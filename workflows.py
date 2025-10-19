import json
from pathlib import Path
from typing import Optional

from google import genai
from git import Repo, GitCommandError, InvalidGitRepositoryError, NoSuchPathError

from RepoHelpers import get_git_root, fetch_from_remote, anything_staged, sanitize_staged_secrets_in_index, llm_scan_staged_secrets_in_index, generate_commit_message

# Load config
with open('config.json', 'r') as f:
    config = json.load(f)

gemini_config = config.get('gemini')
api_key = gemini_config.get('key')
model = gemini_config.get('model')

# Auto commit
def auto_commit(repo_path: Optional[str]) -> dict:

    # Make sure we are looking at a repo
    if not repo_path:
        # return "Please open Visual Studio Code first before trying this"
        return {
            "ok": False,
            "error": "Please open Visual Studio Code first before trying this",
            "path": repo_path,
        }

    # Check if cwd is a git repo
    repo = get_git_root(repo_path)

    # Exit early if not in a git repo
    if repo is None:
        print('Not a git repo')
        return {
            "ok": False,
            "error": f"Not a git repository: {repo_path}",
            "path": repo_path
        }

    # Fetch from remote
    if repo.remotes:
        try:
            fetch_from_remote(repo)
        except Exception as e:
            print(f'Fetch failed: {e}\n')
            return {
                "ok": True,
                "warn": f"Repository does not have a remote: {repo_path}",
                "path": repo_path,
            }

    # Stage changes
    print("Staging all changes")
    repo.git.add(A=True)

    # Check if anything got staged
    if not anything_staged(repo):
        print('No changes have been made')
        return {"ok": True, "message": "Nothing to commit", "path": repo_path}

    return_message = ""

    # Scan for secrets
    print('Scanning for secrets (regex)')
    sanitized = sanitize_staged_secrets_in_index(repo)

    if sanitized:
        print('Sanitized staged secrets in: ')
        for i in sanitized:
            print(f'\t- {i}')

        return_message = f"I've found and redacted secrets in the following files:\n"
        for i in sanitized:
            return_message += f'{i["path"]} '

        return_message += '\n\n'

    # (Maybe) LLM scans for secrets
    print('Scanning for secrets (Gemini)')
    llm_results = llm_scan_staged_secrets_in_index(repo)

    if llm_results:
        print("Sanitized staged secrets in LLM pass:")

        for r in llm_results:
            print(f"\t-{r['path']} ({r['replaced_count']} replacements)")

            for note in r.get("notes", [])[:3]:
                print(f'\t\t -- {note}')

        if return_message == "":
            return_message = "I've found and redacte secrets in the following files:\n"
            for i in llm_results:
                return_message += f'{i["path"]}'
        else:
            return_message += "I also found some trickier secrets in:\n"
            for i in llm_results:
                return_message+= f'{i["path"]}'

    # Generate commit message
    print("Generating commit message")
    commit_message = generate_commit_message(repo, sanitized, llm_results)
    print(f'Commit message:\n{commit_message}')

    # Commit the changes
    try:
        commit_obj = repo.index.commit(commit_message)
        print(f"✅ Created commit: {commit_obj.hexsha[:8]} - {commit_obj.summary}")

        return_message += f"\n\n\nI've successfully commited the repository with the commit message:\n{commit_message}"
    except Exception as e:
        print(f"❌ Failed to commit changes: {e}")
        return {
            "ok": False,
            "error": f"auto_commit failed while committing: {e}",
            "path": repo_path,
        }

    # Push the commit
    try:
        if repo.remotes:
            try:
                remote = repo.remotes.origin
            except:
                remote = repo.remotes[0]

            print(f'Pushing to remote {remote.name}...')
            push_info =remote.push()

            if push_info and push_info[0].flags & push_info[0].ERROR:
                print(f'Push error: {push_info[0].summary}')
                return_message += f"\n\nUnfortunatley it looks like we've ran into a push error. I got the error:\n{push_info[0].summary}"
            else:
                print(f'Successfully pushed to {remote.name}')
                return_message += f"\nAnd your changes have successfully been pushed to remote"
        else:
            print(f'No remote configured, committed locally only')
    except GitCommandError as e:
        print(f'Push failed: {e}')

    return {"ok": True, "message": return_message, "path": repo_path}


# New repo
def new_repo(repo_name, repo_desc, is_local=False):
    pass

# Clone and setup repo

# Auto docs

# Process Manager

# Log reader

