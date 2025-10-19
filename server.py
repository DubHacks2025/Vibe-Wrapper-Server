from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import urllib.request

last = {"path": None, "ts": None}


def get_cwd(server_url: str = "http://127.0.0.1:8765") -> str | None:
    """Return the most recently active VS Code project directory, or None if none yet."""
    try:
        with urllib.request.urlopen(f"{server_url}/active-project") as resp:
            data = json.load(resp)
            return (data.get("data") or {}).get("path")
    except Exception as e:
        # print(f"[get_cwd] Error getting active project: {e}")
        return None


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/project-focus":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        try:
            data = json.loads(body)
            new_path = data.get("path")
            new_ts = data.get("ts")

            # Only print if it actually changed
            if new_path and new_path != last.get("path"):
                print(f"[Updated CWD] {new_path}")
                pass

            last["path"] = new_path
            last["ts"] = new_ts

            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"ok": true}')

        except Exception as e:
            # print(f"[Error parsing POST] {e}")
            self.send_response(400)
            self.end_headers()

    def do_GET(self):
        if self.path != "/active-project":
            self.send_response(404)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True, "data": last}).encode())

def main():
    print("Server listening on http://127.0.0.1:8765 ...")
    HTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
    
if __name__ == "__main__":
    main()
