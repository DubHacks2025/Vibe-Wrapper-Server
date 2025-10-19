# actions/files.py
import os, sys, pathlib, subprocess, shlex, webbrowser

def _platform_open(path_str: str):
    if sys.platform.startswith("darwin"):
        subprocess.run(["open", path_str], check=True)
    elif os.name == "nt":
        subprocess.run(f'start "" {shlex.quote(path_str)}', shell=True, check=True)
    else:
        subprocess.run(["xdg-open", path_str], check=True)

def open_path(raw_path: str) -> dict:
    p = pathlib.Path(os.path.expandvars(os.path.expanduser(raw_path)))
    try:
        if p.exists():
            _platform_open(str(p))
            return {"ok": True, "opened": str(p)}
    except subprocess.CalledProcessError as e:
        return {"ok": False, "error": f"Open command failed: {e}", "path": str(p)}
    except Exception as e:
        return {"ok": False, "error": str(e), "path": str(p)}

def open_url(url: str) -> dict:
    try:
        webbrowser.open(url)
        return {"ok": True, "opened": url}
    except Exception as e:
        return {"ok": False, "error": str(e), "url": url}

if __name__ == "__main__":
    open_path('/Users/y/Desktop/test.pdf')
