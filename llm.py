# llm.py
import os
import json
# from dotenv import load_dotenv
from google import genai
from google.genai import types
import whisperSTT
# --- Config ---
# If you keep a custom env file, set GEMINI_ENV_PATH; else default to ".env"
# ENV_PATH = os.getenv("GEMINI_ENV_PATH", "/Users/y/Desktop/gemini.env")
# load_dotenv(ENV_PATH) if os.path.exists(ENV_PATH) else load_dotenv()

with open('config.json', 'r') as f:
    config = json.load(f)

gemini_config = config.get("gemini")

API_KEY = gemini_config.get('key')
MODEL_ID = gemini_config.get('model')

# Optional: bring in your system/few-shot content if you actually use them
SYSTEM = open("prompts/system_strict_json.txt").read()
FEWSHOT = open("prompts/fewshot.txt").read()

# --- Client ---
client = genai.Client(api_key=API_KEY)

# --- System instruction (tightened) ---
system_instruction = """
You are a command planner. Convert the user’s voice request into a single JSON object following the schema.

Rules:
- Output ONLY JSON. No backticks, no prose, no comments.
- Prefer specific, minimal commands.
- If potentially destructive (delete, kill, rm, overwrite), return a `type` that is unknown to force rejection.
- Default safety: never run arbitrary shell unless the command matches allowlist templates.
- Infer missing fields conservatively.
- Use meta.confidence in [0,1].

- For opening files:
    ALWAYS ALWAYS include the full filename with extension in the file path (like in file_name.pdf format).
    You dont need to specifically write file_name but you need to add that to the end of file_path.
    The default file path(when the user not declared) is Desktop, no matter if it's a file or a folder or anything.

- Strictly follow the name of action as in the fewshot file like open_path, open_url, kill_processes_by_name, process_list, system_resources.
- NEVER use types that are not in the fewshot examples. Only use: open_path, open_url, launch_app, type_text, key_press, run_shell, system_status, process_list, kill_process, kill_processes_by_name, system_resources, file_find, logs_tail, git_update_repo, git_init, git_clone, git_setup, none.
- For closing/quitting applications (Chrome, Firefox, Safari, etc.), ALWAYS use type "kill_processes_by_name" with the correct app name.
- NEVER use "quit_application", "close_app", or any other made-up types.
""".strip()


# Generation config: force JSON mime; optionally lower temperature for stricter format
chat_config = types.GenerateContentConfig(
    system_instruction=system_instruction,
    response_mime_type="application/json",
    # temperature=0.2,  # uncomment for stricter formatting
)

chat = client.chats.create(
    model=MODEL_ID,
    config=chat_config,
)

def generate_json():
    # 1) Get voice text
    user_prompt = whisperSTT.take_prompt()

    # 2) Build the actual prompt once
    prompt = (FEWSHOT.strip() + user_prompt) if FEWSHOT else user_prompt

    try:
        response = chat.send_message(prompt)

        text = getattr(response, "text", None)

        if not text and hasattr(response, "candidates") and response.candidates:
            parts = []
            for c in response.candidates:
                if getattr(c, "content", None) and getattr(c.content, "parts", None):
                    for p in c.content.parts:
                        if getattr(p, "text", None):
                            parts.append(p.text)
            text = "\n".join(parts) if parts else None

        if not text:
            raise RuntimeError("Model returned no text. Inspect `response` object for details.")

        # Parse JSON
        obj = json.loads(text)

        # Optional: jsonschema.validate(obj, schema)
        return obj  # return a dict

    except Exception as e:
        # Surface useful debugging info
        print(f"[ERROR] {e}")
        return {"type": "error", "error": str(e)}

if __name__ == "__main__":
    result = generate_json()
    print(json.dumps(result, indent=2))
