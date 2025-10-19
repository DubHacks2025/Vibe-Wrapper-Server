import re
import subprocess
import json
import os
import textwrap

from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any

from git import Repo, GitCommandError, InvalidGitRepositoryError, NoSuchPathError, BadName
from google import genai

from tqdm import tqdm

with open('config.json', 'r') as f:
    config = json.load(f)

gemini_config = config.get('gemini')
api_key = gemini_config.get('key')
model = gemini_config.get('model')

SECRET_TOKEN_PATTERNS = [
    r"AKIA[0-9A-Z]{16}",  # AWS Access Key ID
    r"ASIA[0-9A-Z]{16}",  # AWS Temp Key ID
    r"AIza[0-9A-Za-z_\-]{35}",  # Google/Gemini API key
    r"ghp_[A-Za-z0-9]{36}",  # GitHub classic PAT
    r"github_pat_[A-Za-z0-9_]{82}",  # GitHub fine-grained PAT
    r"xox[baprs]-[A-Za-z0-9-]{10,48}",  # Slack token
    r"sk_live_[0-9A-Za-z]{24,}",  # Stripe live secret
    r"sk-[A-Za-z0-9]{20,48}",  # OpenAI style
    r"(?i:Bearer\s+[A-Za-z0-9\-\._=]{20,})",  # Bearer tokens
    r"\b[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{8,}\b",  # JWT tokens
    r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{8,}\b",  # JWT tokens
    r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{8,}(?![A-Za-z0-9_-])",  # JWT token
    r"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9]{8,19}(?![A-Za-z0-9_-])",  # OpenAI short token
    r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}(?:\.[A-Za-z0-9_-]{8,})?(?![A-Za-z0-9_-])", # JWT tokn
]

KV_VALUE_PATTERNS = [
    (
        re.compile(
            r'([A-Za-z0-9_.-]{2,}\s*[:=]\s*)(["\']?)([A-Za-z0-9_\-\/\+=]{16,})(\2)'
        ),
        1,
        2,
        3,
        4,
    ),
    (
        re.compile(
            r'((?:export\s+)?[A-Za-z0-9_.-]{2,}\s*[:=]\s*)(["\'`]?)(sk-[A-Za-z0-9]{8,48})(\2)',
            re.IGNORECASE,
        ),
        1,  # prefix
        2,  # opening quote/backtick
        3,  # value
        4,  # closing quote/backtick (backref to 2)
    ),
]

# Get the repo if it exists
def get_git_root(path='.') -> Optional[Repo]:
    path = Path(path).resolve()
    
    try:
        # Check if cwd is in a Git repo and get the repo
        repo = Repo(path, search_parent_directories=True)
        
        return repo
    except (InvalidGitRepositoryError, NoSuchPathError):
        return None

# Fetch from remote if it exists
def fetch_from_remote(repo: Repo) -> bool:
    remotes = repo.remotes
    
    # Return false if repo is local and doesn't have any remotes
    if not remotes:
        print('Repo is local and doesn\'t have a remote')
        return False
    
    remote = None
    try:
        remote = repo.remotes.origin
    except AttributeError:
        remote = remotes[0]
        
    try:
        remote.fetch()
        return True
    except GitCommandError as e:
        print(f'Failed to fetch: {e}')
        return False

# Check if any changes are staged
def anything_staged(repo: Repo) -> bool:
    try:
        staged = repo.git.diff('--cached', '--name-only').splitlines()
        return bool(staged)
    except:
        # This runs when we do our first commit in a new repo
        return bool(repo.index.entries)

# Only scan text apprent files, skip any binary files
def _is_probably_text(data: bytes) -> bool:
    if b"\x00" in data:
        return False
    try:
        data.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False

# Change anything that looks like an api key to "api_key"
def _sanitize_text(s: str) -> Tuple[str, bool]:
    changed = False
    
    # Try to preserve keys: replace only values after ':' or '='
    for rx, g_prefix, g_open, g_value, g_suffix in KV_VALUE_PATTERNS:
        def repl(m):
            nonlocal changed
            changed = True
            openq = m.group(g_open) or ''
            closeq = m.group(g_suffix) or ''
            return m.group(g_prefix) + openq +"api_key" + closeq
        
        s2 = rx.sub(repl, s)
        s, changed = s2, (changed or s2 != s)
        
    # Blanket replace raw tokens that look like secrets
    before = s
    token_union = re.compile('|'.join(f'(?:{p})' for p in SECRET_TOKEN_PATTERNS))
    s = token_union.sub('api_key', s)
    
    if s != before:
        changed = True
        
    return s, changed

# Return the blob mode for the index entry
def _blob_mode_from_index(repo: Repo, path: str) -> str:
    entry = repo.index.entries.get((path, 0))
    
    if entry:
        return f'{entry.mode:06o}'
    
    # Default to regular file if missing
    return '100644'

# Scan staged files for any secrets, and if there is a secret replaec it with 'api_key' in the index only
def sanitize_staged_secrets_in_index(repo: Repo) -> List[Dict[str, Any]]:
    modified: List[Dict[str, Any]] = []
    
    # Get list of staged paths (name only)
    try: 
        staged_paths = repo.git.diff('--name-only', '--cached').splitlines()
        staged_paths = [str(p) for p in staged_paths]
    except:
        # Initial commit: Use index for entries
        staged_paths = [str(p) for (p, _) in repo.index.entries.keys()]
        
    root = Path(repo.working_tree_dir or '.')
    cwd_str = str(root)
    
    for path in staged_paths:
        path_str = str(path)
        
        # Skip files that are being deleted. Ensure file is in index
        if (path_str, 0) not in repo.index.entries:
            continue
        
        # Read the staged blob content
        try:
            raw = repo.git.show(f':{path_str}')
            data = raw.encode('utf-8', errors='ignore')
        except:
            # Fall back to working tree if show fails
            wt = (root / path_str)
            
            if not wt.exists() or not wt.is_file():
                continue
            
            data = wt.read_bytes()
            
        # Only process textish files
        if not _is_probably_text(data):
            continue
        
        text = data.decode('utf-8', errors='replace')
        sanitized, changed = _sanitize_text(text)
        
        # Skip if nothing changed
        if not changed:
            continue
        
        # Modify the index to remove api keys
        # 1) git hash-object -w --stdin -> returns blob id
        p1 = subprocess.run(
            ['git', 'hash-object', '-w', '--stdin'],
            cwd=cwd_str,
            input=sanitized.encode('utf-8'),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        if p1.returncode != 0:
            continue
        
        blob_id = p1.stdout.decode().strip()
        
        # 2) git update-index --cacheinfo <mode> <blob> <path>
        mode = _blob_mode_from_index(repo, path_str)
        p2 = subprocess.run(
            ['git', 'update-index', '--cacheinfo', mode, blob_id, path_str],
            cwd=cwd_str,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        if p2.returncode == 0:
            modified.append({'path': path_str, 'replaced': True})
            
    return modified

def llm_scan_staged_secrets_in_index(repo: Repo, max_chars_per_call: int = 60000) -> list[dict]:
    LLM_PROMPT_PREAMBLE = """You are a precise code auditor.
Given a file CHUNK, identify any secrets that look like API keys, tokens, client secrets, or credentials.
Return ONLY JSON with this schema (no extra text):

{
  "findings": [
    {
      "start": <integer char offset in the PROVIDED CHUNK>,
      "end": <integer char offset in the PROVIDED CHUNK>,
      "kind": "<short label, e.g. 'token'|'api_key'|'client_secret'>",
      "reason": "<why this looks sensitive>",
      "snippet": "<the exact substring you flagged>"
    }
  ]
}

Rules:
- Offsets are character indices in the CHUNK you are given, not the whole file.
- Only include items you are at least 60% confident are secrets.
- Prefer values (right-hand side of = or :) rather than keys.
- Avoid false positives like URLs without tokens, comments about keys, or placeholders.
- If nothing is found, return {"findings": []}.
"""

    def _chunk_text(s: str, max_chars: int = 60000, overlap: int = 200) -> list[tuple[int, str]]:
        """Yield (offset, chunk). Offsets are start positions in the full string."""
        if len(s) <= max_chars:
            return [(0, s)]
        out, i, n = [], 0, len(s)
        while i < n:
            j = min(i + max_chars, n)
            out.append((i, s[i:j]))
            if j == n:
                break
            i = max(0, j - overlap)
        return out

    def _apply_replacements_by_ranges(text: str, ranges: list[tuple[int, int]], replacement: str = "api_key") -> str:
        """Apply [start,end) replacements descending by start so indices remain valid."""
        out = text
        for (start, end) in sorted(ranges, key=lambda r: r[0], reverse=True):
            if 0 <= start < end <= len(out):
                out = out[:start] + replacement + out[end:]
        return out

    def _extract_findings_from_response(resp_text: str) -> list[dict]:
        try:
            data = json.loads(resp_text)
        except Exception:
            return []
        items = data.get("findings", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        out = []
        for it in items:
            try:
                start = int(it["start"]); end = int(it["end"])
                kind = str(it.get("kind", "secret"))
                reason = str(it.get("reason", ""))
                snippet = str(it.get("snippet", ""))
                out.append({"start": start, "end": end, "kind": kind, "reason": reason, "snippet": snippet})
            except Exception:
                continue
        return out

    results: list[dict] = []

    # Get staged paths
    try:
        staged_paths = repo.git.diff('--name-only', '--cached').splitlines()
    except:
        staged_paths = [str(p) for (p, _) in repo.index.entries.keys()]

    if not staged_paths:
        return results

    root = Path(repo.working_tree_dir or '.')
    cwd_str = str(root)
    client = genai.Client(api_key=api_key)

    for path_str in tqdm(staged_paths, desc='Sanatizing changed files', unit=' File'):
        # Skip deletions or not in index
        if (path_str, 0) not in repo.index.entries:
            continue

        # Read staged blob
        try:
            raw = repo.git.show(f':{path_str}')
            data = raw.encode('utf-8', errors='ignore')
        except:
            wt = (root / path_str)

            if not wt.exists() or not wt.is_file():
                continue

            data = wt.read_bytes()

        # Only process text files
        if not _is_probably_text(data):
            continue

        text = data.decode('utf-8', errors='replace')
        chunks = _chunk_text(text, max_chars=max_chars_per_call, overlap=200)

        all_ranges: list[tuple[int, int]] = []
        notes: list[str] = []

        for base, chunk in chunks:
            try:
                resp = client.models.generate_content(
                    model=model,
                    contents=[
                        {
                            "role":"user",
                            "parts": [
                                { "text": LLM_PROMPT_PREAMBLE },
                                { "text": f"CHUNK:\n{chunk}"}
                            ]
                        }
                    ],
                    # TODO: Maybe remove?
                    config={
                        "response_mime_type": "application/json"
                    }
                )

                resp_text = getattr(resp, "text", "") or ""
                findings = _extract_findings_from_response(resp_text)

                # Map chunk offsets
                for f in tqdm(findings, desc='Sanatizing findings', unit=' Finding'):
                    s, e = f['start'], f['end']

                    if 0 <= s < e < len(chunk):
                        candidate = chunk[s:e]

                        # If snippet provided but not aligned, attempt loose locate
                        snip = f.get("snippet") or ""
                        if snip and snip not in candidate:
                            idx = chunk.find(snip)

                            if idx != -1:
                                s, e = idx, idx + len(snip)
                                candidate = chunk[s:e]

                        if len(candidate.strip()) >= 8:  # avoid trivial strings
                            all_ranges.append((base + s, base + e))
                            notes.append(
                                f"{path_str}: {f.get('kind','secret')} → {f.get('reason','')}"
                            )
            except Exception as e:
                notes.append(f"LLM error on chunk: {e}")

        if not all_ranges:
            continue

        # TODO: Remove LLM part, left in for testing
        new_text = _apply_replacements_by_ranges(text, all_ranges, replacement='api_key_llm')

        # Make sure text was changed
        if new_text == text:
            continue

        p1 = subprocess.run(
            ['git', 'hash-object', '-w', '--stdin'],
            cwd=cwd_str,
            input=new_text.encode('utf-8'),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        if p1.returncode != 0:
            results.append({ "path": path_str, "replaced_count": 0, "notes": notes + ['hash-object failed']})
            continue

        blob_id = p1.stdout.decode().strip()
        mode = _blob_mode_from_index(repo, path_str)

        p2 = subprocess.run(
            ['git', 'update-index', '--cacheinfo', mode, blob_id, path_str],
            cwd=cwd_str,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        if p2.returncode == 0:
            results.append(
                {"path": path_str, "replaced_count": len(all_ranges), "notes": notes}
            )
        else:
            results.append(
                {
                    "path": path_str,
                    "replaced_count": 0,
                    "notes": notes + ["update-index failed"],
                }
            )

    return results

def _read_small_file(path: Path, limit: int = 40_000) -> str:
    try:
        if not path.exists() or not path.is_file():
            return ""
        data = path.read_bytes()
        if len(data) > limit:
            return data[:limit].decode("utf-8", errors="replace") + "\n\n[TRUNCATED]"
        return data.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _primary_language(repo_root: Path) -> str:
    exts = {}
    # scan lightly to keep things fast
    for p in repo_root.rglob("*"):
        try:
            if (
                p.is_file()
                and not p.name.startswith(".")
                and p.stat().st_size < 2_000_000
            ):
                ext = p.suffix.lower()
                if ext:
                    exts[ext] = exts.get(ext, 0) + 1
        except Exception:
            continue
    if not exts:
        return "unknown"
    ext = max(exts.items(), key=lambda kv: kv[1])[0]
    return {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".go": "go",
        ".rb": "ruby",
        ".rs": "rust",
        ".java": "java",
        ".cpp": "cpp",
        ".c": "c",
        ".cs": "csharp",
        ".php": "php",
    }.get(ext, ext.lstrip("."))


def _staged_name_status(repo: Repo) -> list[tuple[str, str]]:
    out = []
    try:
        lines = repo.git.diff("--cached", "--name-status").splitlines()
        for ln in lines:
            parts = ln.split("\t", 1)
            if len(parts) == 2:
                out.append((parts[0].strip(), parts[1].strip()))
    except Exception:
        pass
    return out


def _staged_patch(repo: Repo, max_chars: int = 80_000) -> str:
    try:
        patch = repo.git.diff("--cached", "-U2")
        return (
            patch
            if len(patch) <= max_chars
            else patch[:max_chars] + "\n\n[PATCH TRUNCATED]"
        )
    except Exception:
        return ""


def _collect_nearby_context(
    root: Path, staged_paths: list[str], max_files: int = 12
) -> dict:
    """
    Dynamically gather small, likely-useful context files near what's staged,
    plus a few root-level hints. The LLM decides what's relevant.
    """
    ctx: dict[str, str] = {}
    seen: set[Path] = set()

    # Root-level hints if present
    root_hints = [
        "README.md",
        "README",
        "LICENSE",
        "CONTRIBUTING.md",
        "pyproject.toml",
        "requirements.txt",
        "Pipfile",
        "package.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "go.mod",
        "Cargo.toml",
        "composer.json",
        "Makefile",
        "CMakeLists.txt",
    ]
    for name in root_hints:
        p = root / name
        if p.exists() and p.is_file():
            ctx[name] = _read_small_file(p)
            seen.add(p)
        if len(ctx) >= 6:  # keep it lean
            break

    # Nearby hints for each staged file (parent config/build files)
    neighbor_names = {
        "Makefile",
        "pyproject.toml",
        "requirements.txt",
        "package.json",
        "Cargo.toml",
        "go.mod",
        "tsconfig.json",
        "setup.py",
        "setup.cfg",
        ".pre-commit-config.yaml",
        ".flake8",
        ".editorconfig",
    }
    for path_str in staged_paths:
        pp = (root / path_str).parent
        for cand in neighbor_names:
            p = pp / cand
            if p.exists() and p.is_file() and p not in seen:
                rel = str(p.relative_to(root))
                ctx[rel] = _read_small_file(p)
                seen.add(p)
                if len(ctx) >= max_files:
                    return ctx
    return ctx


def collect_project_context_dynamic(repo: Repo, staged_paths: list[str]) -> dict:
    root = Path(repo.working_tree_dir or ".")
    branch = "DETACHED"
    try:
        if not repo.head.is_detached:
            branch = getattr(repo.head, "reference", None).name
    except Exception:
        pass

    ctx = {
        "repo_name": root.name,
        "branch": branch,
        "primary_language": _primary_language(root),
        "nearby_context": _collect_nearby_context(root, staged_paths),
    }
    return ctx


def _fallback_commit_message(
    staged: list[tuple[str, str]], sanitized: list[dict], llm_results: list[dict]
) -> str:
    added = sum(1 for s, _ in staged if s.upper().startswith("A"))
    modified = sum(1 for s, _ in staged if s.upper().startswith("M"))
    deleted = sum(1 for s, _ in staged if s.upper().startswith("D"))
    sec_paths = {d["path"] for d in (sanitized or [])}
    sec_paths |= {d["path"] for d in (llm_results or []) if "path" in d}

    subject = "chore: commit staged changes"
    if sec_paths:
        subject = "chore(security): sanitize secrets and commit changes"
    body = []
    if added or modified or deleted:
        body.append(f"- files: +{added} ~{modified} -{deleted}")
    if sec_paths:
        body.append(f"- sanitized secrets in {len(sec_paths)} file(s)")
    body.append("- auto-generated message (fallback)")
    return subject + "\n\n" + "\n".join(body)


def generate_commit_message(
    repo: Repo,
    sanitized: list[dict] | None,
    llm_results: list[dict] | None,
    max_ctx_chars: int = 110_000,
) -> str:
    """
    Build a Conventional Commits-style message with dynamic repo context.
    Uses module-level `api_key` and `model` variables (already loaded from config).
    Falls back to a deterministic message if the model fails.
    """
    staged = _staged_name_status(repo)
    if not staged:
        return "chore: no-op (nothing staged)"

    staged_paths = [p for _, p in staged]
    ctx = collect_project_context_dynamic(repo, staged_paths)
    patch = _staged_patch(repo, max_chars=min(80_000, max_ctx_chars))

    # Compact context blob
    ctx_blob = {
        "repo_name": ctx["repo_name"],
        "branch": ctx["branch"],
        "primary_language": ctx["primary_language"],
        "staged": staged[:400],
        "sanitized_paths": sorted({d["path"] for d in (sanitized or [])}),
        "llm_sanitized": [
            {"path": r["path"], "count": int(r.get("replaced_count", 0))}
            for r in (llm_results or [])
            if "path" in r
        ][:200],
        "context_files": ctx["nearby_context"],  # the LLM decides importance
    }

    SYSTEM = textwrap.dedent(
        """\
    You are a commit message generator that writes clear messages following Conventional Commits.
    Output plain text ONLY: a subject line (<=72 chars), optional blank line, and a short body.
    If secrets were sanitized, use type "chore" with scope "(security)" and mention it in the body.
    Use present tense and imperative mood (e.g., "sanitize", "add", "fix").
    Avoid code fences, markdown headers, or JSON in the output.
    """
    )

    RULES = textwrap.dedent(
        """\
    Guidelines:
    - Subject: format: type(scope): description (e.g., "feat(ui): add dark mode").
    - Summarize WHAT changed and WHY in 1-5 short lines in the body.
    - Refer to files or modules only when helpful; avoid noisy path lists.
    - If secrets were removed/masked, mention the count of affected files.
    - No trailers unless needed for BREAKING CHANGE.
    - Do not format anything, everything should be in plain, natural english. Do not use markdown formatting.
    """
    )

    USER = textwrap.dedent(
        f"""\
    Project context (auto-collected from staged files and nearby configs):
    {json.dumps({k:v for k,v in ctx_blob.items() if k != "staged"}, ensure_ascii=False)[:max_ctx_chars//2]}

    Staged changes (name-status):
    {json.dumps(ctx_blob["staged"], ensure_ascii=False)[:max_ctx_chars//4]}

    Unified diff (may be truncated):
    {patch}

    {RULES}
    Write the commit message now.
    """
    )

    try:
        client = genai.Client(api_key=api_key)  # uses module-level api_key
        resp = client.models.generate_content(
            model=model,  # uses module-level model
            contents=[
                {"role": "user", "parts": [{"text": SYSTEM}]},
                {"role": "user", "parts": [{"text": USER}]},
            ],
        )
        msg = (getattr(resp, "text", None) or "").strip()
        if not msg:
            raise RuntimeError("empty LLM response")

        # light cleanup
        if "```" in msg:
            msg = msg.replace("```", "").strip()
        lines = [ln.rstrip() for ln in msg.splitlines()]
        if not lines or not lines[0]:
            raise RuntimeError("invalid commit message")
        if len(lines[0]) > 72:
            lines[0] = lines[0][:72]
        # normalize: subject, optional blank line, rest
        normalized = "\n".join(
            [lines[0]] + ([] if len(lines) == 1 or lines[1] == "" else [""]) + lines[1:]
        )
        return normalized
    except Exception as e:
        print(f'\n==========\nEXCEPTION: {str(e)}\n==========\n')
        return _fallback_commit_message(staged, sanitized or [], llm_results or [])