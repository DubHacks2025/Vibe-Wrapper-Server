#!/usr/bin/env python3
"""
generate_test_keys.py

Create a test workspace with many example API keys and secret placements.
Some keys match the sanitizer's current regexes, others are intentionally
different so they will NOT be caught by your current rules.

Usage:
    python generate_test_keys.py
"""

from pathlib import Path
import json
import yaml  # pyyaml (only used to write YAML); if not installed the YAML file will be plain text fallback
import base64
import secrets
import os

OUT = Path(r"/Users/alexjshepler/Downloads/test")
OUT.mkdir(exist_ok=True)


def mk(keyname: str, value: str, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{keyname}={value}\n")


# --------------- helpers that generate fake tokens ---------------
def fake_ghp():
    return "ghp_" + secrets.token_hex(18)  # matches ghp_[A-Za-z0-9]{36}


def fake_sk_long():
    return "sk-" + secrets.token_hex(24)  # matches sk-[A-Za-z0-9]{20,48}


def fake_sk_short():
    return "sk-" + secrets.token_hex(6)  # short; may NOT be caught by long-only regex


def fake_ak():
    # AWS AKIA pattern 16 caps/digits
    return "AKIA" + secrets.token_hex(8).upper()[:16]


def fake_gapi():
    return "AIza" + secrets.token_urlsafe(27)[:35]  # approximate length


def fake_generic_long():
    return secrets.token_urlsafe(32)


def fake_jwt():
    # Create a JWT-like string (header.payload.signature) base64-ish
    header = (
        base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=").decode()
    )
    payload = (
        base64.urlsafe_b64encode(b'{"sub":"1234567890","name":"Test"}')
        .rstrip(b"=")
        .decode()
    )
    sig = secrets.token_urlsafe(32)
    return f"{header}.{payload}.{sig}"


def fake_url_token():
    return "token=" + fake_ghp()


# --------------- create files ---------------
# .env (typical env file)
env_path = OUT / ".env"
env_path.write_text("", encoding="utf-8")
mk("OPENAI_KEY", fake_sk_long(), env_path)  # should be caught
mk("OPENAI_KEY_SHORT", fake_sk_short(), env_path)  # may not be caught
mk("GITHUB_PAT", fake_ghp(), env_path)  # should be caught
mk("AWS_KEY", fake_ak(), env_path)  # should be caught
mk("GENERIC_TOKEN", fake_generic_long(), env_path)  # may or may not be caught

# config.json (JSON-style key)
config_path = OUT / "config.json"
config = {
    "openai": {"key": fake_sk_long()},
    "legacy_short": {"key": fake_sk_short()},
    "service": {"gcloud": fake_gapi()},
}
config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

# secrets.json (another JSON shape)
secrets_json_path = OUT / "secrets.json"
secrets_json_path.write_text(
    json.dumps(
        {"stripe_secret": "sk_live_" + secrets.token_hex(16), "jwt": fake_jwt()},
        indent=2,
    ),
    encoding="utf-8",
)

# credentials.yml (YAML)
creds_path = OUT / "credentials.yml"
try:
    yaml.safe_dump(
        {
            "github": {"token": fake_ghp()},
            "aws": {"access_key": fake_ak(), "secret": fake_generic_long()},
        },
        open(creds_path, "w", encoding="utf-8"),
    )
except Exception:
    # fallback plain text if pyyaml not installed
    creds_path.write_text(
        f"github.token: {fake_ghp()}\naws.access_key: {fake_ak()}\n", encoding="utf-8"
    )

# script.sh (shell with exported vars)
script_path = OUT / "scripts" / "deploy.sh"
script_path.parent.mkdir(parents=True, exist_ok=True)
script_path.write_text(
    "#!/usr/bin/env bash\n"
    f"export OPENAI_API_KEY='{fake_sk_long()}'\n"
    f"export LEGACY_KEY='{fake_sk_short()}'\n"
    "echo 'deployed'\n",
    encoding="utf-8",
)
os.chmod(script_path, 0o755)

# README.md (contains example inlined and URL)
readme_path = OUT / "README.md"
readme_path.write_text(
    "# Example project\n\n"
    "You might temporarily paste keys like this:\n\n"
    f"- `API_KEY={fake_sk_long()}` (should be flagged)\n"
    f"- `legacy_short=sk-{secrets.token_hex(6)}` (likely not flagged)\n\n"
    f"Also a URL: https://api.example.com/data?{fake_url_token()}\n",
    encoding="utf-8",
)

# url token file
url_path = OUT / "url_tokens.txt"
url_path.write_text(f"https://service/?{fake_url_token()}\n", encoding="utf-8")

# jwt token file
jwt_path = OUT / "tokens" / "jwt.txt"
jwt_path.parent.mkdir(parents=True, exist_ok=True)
jwt_path.write_text(fake_jwt() + "\n", encoding="utf-8")

# Create a "hardcoded" python file (simple variant)
hardcoded_py = OUT / "hardcoded" / "hardcode_example.py"
hardcoded_py.parent.mkdir(parents=True, exist_ok=True)
hardcoded_py.write_text(
    'API_KEY = "%s"\n\n'
    "def show_key():\n"
    '    print("Using API key (for testing):", API_KEY)\n\n'
    'if __name__ == "__main__":\n'
    "    show_key()\n" % fake_sk_long(),
    encoding="utf-8",
)

# Create another file with keys embedded inside JSON in a JS file (different shape)
js_path = OUT / "frontend" / "config.js"
js_path.parent.mkdir(parents=True, exist_ok=True)
js_path.write_text(
    "window.__CONFIG__ = {\n"
    f'  "apiKey": "{fake_sk_long()}",\n'
    f'  "shortKey": "{fake_sk_short()}"\n'
    "};\n",
    encoding="utf-8",
)

# Create "obscure" placements that may escape your current patterns
misc_path = OUT / "misc" / "obscure.txt"
misc_path.parent.mkdir(parents=True, exist_ok=True)
misc_contents = "\n".join(
    [
        "plain_secret=superduperlongrandomhash0123456789abcdef",  # generic long token — might be flagged if you add heuristic
        "jwt_like=" + fake_jwt(),
        "url_here=https://example.com?auth=sk-"
        + secrets.token_hex(6),  # short sk- in URL (may be missed)
        "base64_secret=" + base64.b64encode(secrets.token_bytes(24)).decode(),
    ]
)
misc_path.write_text(misc_contents, encoding="utf-8")

print(f"Test workspace created at: {OUT.resolve()}")
print("Files written:")
for p in sorted(OUT.rglob("*")):
    if p.is_file():
        print(" -", p.relative_to(OUT))
