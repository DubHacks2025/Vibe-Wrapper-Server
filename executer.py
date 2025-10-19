#!/usr/bin/env python3
import sys
import json
from typing import Any, Dict

from actions.files import open_path, open_url
from actions.process_manager import list_processes, kill_process, kill_processes_by_name, get_system_resources
from actions.focus_mode import enable_focus_mode, disable_focus_mode, get_focus_status, set_focus_duration
from actions.screenshot import take_screenshot, screenshot_and_summarize, screenshot_and_translate, screenshot_and_describe, take_and_analyze_screenshot

from workflows import auto_commit

from server import get_cwd

import llm

ACTIONS = {
    "open_path": lambda args: open_path(args.get("path", "")),
    "open_url": lambda args: open_url(args.get("url", "")),
    "process_list": lambda args: list_processes(
        limit=args.get("limit", 50),
        sort_by=args.get("sort_by", "cpu")
    ),
    "kill_process": lambda args: kill_process(
        pid=args.get("pid"),
        force=args.get("force", False)
    ),
    "kill_processes_by_name": lambda args: api_key(
        name=args.get("name"),
        force=args.get("force", False)
    ),
    "system_resources": lambda args: api_key(),
    "enable_focus_mode": lambda args: api_key(),
    "disable_focus_mode": lambda args: api_key(),
    "focus_status": lambda args: api_key(),
    "set_focus_duration": lambda args: api_key(args.get("minutes", 30)),
    "take_screenshot": lambda args: take_screenshot(args.get("save_path")),
    "screenshot_and_summarize": lambda args: api_key(args.get("language", "english")),
    "screenshot_and_translate": lambda args: api_key(args.get("language", "english")),
    "screenshot_and_describe": lambda args: api_key(),
    "take_and_analyze_screenshot": lambda args: api_key(args.get("action", "summarize"), args.get("language", "english"), args.get("save_path")),
    "commit": lambda args: auto_commit(get_cwd())
}

def normalize_args(payload: Dict[str, Any]) -> Dict[str, Any]:
    # Accept either "args" or "parameters"
    args = payload.get("args")
    if args is None:
        args = payload.get("parameters", {})
    return args or {}

def main():

    # 1) Get JSON command from LLM
    try:
        payload = llm.generate_json()
        if not isinstance(payload, dict):
            raise ValueError("llm.generate_json() did not return a JSON object.")
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"Failed to get JSON from LLM: {e}"}))
        sys.exit(1)

    # 2) Validate basic schema
    t = payload.get("type")
    args = normalize_args(payload)

    # Map common incorrect types to correct ones
    type_mapping = {
        "quit_application": "kill_processes_by_name",
        "close_app": "kill_processes_by_name",
        "close_application": "kill_processes_by_name",
        "quit_app": "kill_processes_by_name",
        "open_google": "open_url",
        "search_google": "open_url",
        "open_youtube": "open_url",
        "focus_mode": "enable_focus_mode",
        "do_not_disturb": "enable_focus_mode",
        "turn_on_focus": "enable_focus_mode",
        "turn_off_focus": "disable_focus_mode",
        "screenshot": "take_screenshot",
        "capture_screen": "take_screenshot",
        "screen_capture": "take_screenshot",
        "git_update_repo": "commit",
        "git_update": "commit",
        "update_repo": "commit",
        "update_repository": "commit",
        "save_progress": "commit",
        "save_work": "commit",
        "push_changes": "commit",
        "commit_changes": "commit",
        "commit": "commit",
    }

    if t in type_mapping:
        t = type_mapping[t]
        payload["type"] = t

    if not t or t not in ACTIONS:
        print(json.dumps({"ok": False, "error": f"Unsupported or missing type: {t}"}))
        sys.exit(2)

    # 3) Per-command checks
    if t == "open_path" and not args.get("path"):
        print(json.dumps({"ok": False, "error": "Missing required field: args.path"}))
        sys.exit(3)
    if t == "open_url" and not args.get("url"):
        print(json.dumps({"ok": False, "error": "Missing required field: args.url"}))
        sys.exit(3)
    if t == "kill_process" and not args.get("pid"):
        print(json.dumps({"ok": False, "error": "Missing required field: args.pid"}))
        sys.exit(3)
    if t == "kill_processes_by_name" and not args.get("name"):
        print(json.dumps({"ok": False, "error": "Missing required field: args.name"}))
        sys.exit(3)

    # 4) Execute action
    try:
        result = ACTIONS[t](args)
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"Action '{t}' failed: {e}"}))
        sys.exit(4)

    # 5) Normalize result and exit
    if not isinstance(result, dict):
        result = {"ok": False, "error": f"Action '{t}' returned non-dict result"}

    if "ok" not in result:
        result["ok"] = True

    # print(json.dumps(result))
    print(result.get("analysis"))
    # sys.exit(0 if result.get("ok") else 5)

if __name__ == "__main__":
    main()