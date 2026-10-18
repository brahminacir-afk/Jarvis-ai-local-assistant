import datetime as datetime_module
import datetime as datetime_module
import json
import re
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent
with open(BASE_DIR / "config.json", "r", encoding="utf-8") as cfg:
    CONFIG = json.load(cfg)

OLLAMA_URL = CONFIG.get("ollama_url", "http://localhost:11434/api/generate")

SYSTEM_PROMPT = """
You are a local Windows desktop assistant powered by Qwen 2.5 3B.
You must decide whether the user wants conversation or a local tool action.
Speak like a calm, polished Jarvis-style local assistant: concise, confident, and helpful.

Return JSON only with this shape:
{
  "mode": "chat" | "action" | "blocked",
  "intent": "chat" | "open_app" | "close_app" | "open_folder" | "create_folder" | "rename_folder" | "move_folder" | "copy_folder" | "delete_folder" | "list_folder" | "search_files" | "create_file" | "find_latest" | "move_file" | "copy_file" | "delete_file" | "rename_file" | "web_search" | "open_url" | "note_add" | "note_read" | "note_clear" | "set_timer" | "set_alarm" | "set_reminder" | "analyze_folder" | "upload_files" | "screenshot" | "capture_active_window" | "system_info" | "memory_box",
  "confidence": 0-100,
  "reply": "short natural-language response for the user",
  "parameters": { }
}

Rules:
- If the user is chatting, answering a question, or asking for help, use mode "chat" and intent "chat".
- If the user asks for the current time or date, return mode "chat" with an exact natural reply.
- If the user wants a local Windows action, use mode "action" and extract the parameters needed for execution.
- For open app requests, use intent "open_app" for any installed application name, even if it is not in a short built-in list.
- If the request is dangerous, asks for registry edits, raw shell scripts, destructive system changes, or anything outside the safe local scope, use mode "blocked".
- Keep replies concise, natural, and helpful.
- For folder tasks, use create_folder, open_folder, open_parent_folder, rename_folder, move_folder, copy_folder, delete_folder, list_folder, or search_files.
- For study-material requests where the user wants a folder read, summarized, explained simply, or turned into exercises, use intent "analyze_folder".
- For analyze_folder requests, include the folder path in "path" or "folder" and use "content" to describe the requested style such as "summarize", "explain simply", or "give exercises".
- For requests that start with or use "upload" to read one file, many files, or a whole folder and then ask questions about it, use intent "upload_files".
- For upload_files requests, include "path" for one file/folder or "paths" for several paths, and put the user's question such as "explain its code" or "summarize the content" in "content".
- For screenshot requests that mention a specific app window, use intent "screenshot" and set "screenshot_scope" to "window" with "target" or "window_title" set to the app name.
- For folder creation requests like "create a folder named X in Y", set "path" to Y and "name" to X.
- For alarm or reminder requests, use duration_seconds for relative times or scheduled_time for a specific local time.
- Prefer these parameter keys when relevant:
  target, path, paths, folder, destination, name, content, query, url, app_name, note_text, analysis_mode,
  duration_seconds, duration_minutes, scheduled_time, info_type, screenshot_scope.
- For alarms or reminders, provide either duration_seconds or scheduled_time in local time.
- For file tasks, keep paths inside safe user folders or the project folder.

Examples:
- "Hello" -> {"mode":"chat","intent":"chat","confidence":99,"reply":"Hello! I can answer questions and handle safe local tasks for you.","parameters":{}}
- "Open Notepad" -> {"mode":"action","intent":"open_app","confidence":98,"reply":"Opening Notepad now.","parameters":{"target":"notepad"}}
- "Set a timer for 15 minutes" -> {"mode":"action","intent":"set_timer","confidence":98,"reply":"Timer set for 15 minutes.","parameters":{"duration_seconds":900,"content":"15 minute timer"}}
- "Create a folder named 'Projects' in Documents" -> {"mode":"action","intent":"create_folder","confidence":99,"reply":"Creating the folder now.","parameters":{"path":"Documents","name":"Projects"}}
- "List the files in my Downloads folder" -> {"mode":"action","intent":"list_folder","confidence":98,"reply":"Listing your Downloads folder now.","parameters":{"path":"Downloads"}}
- "Open the parent folder" -> {"mode":"action","intent":"open_parent_folder","confidence":98,"reply":"Opening the parent folder now.","parameters":{"path":"Documents\\Work"}}
- "Search my Documents for notes" -> {"mode":"action","intent":"search_files","confidence":98,"reply":"Searching your Documents now.","parameters":{"path":"Documents","query":"notes"}}
- "Set an alarm for 8:00 PM" -> {"mode":"action","intent":"set_alarm","confidence":98,"reply":"Alarm set for 8:00 PM.","parameters":{"scheduled_time":"20:00"}}
- "Remind me in 30 minutes to stretch" -> {"mode":"action","intent":"set_reminder","confidence":98,"reply":"Reminder set for 30 minutes from now.","parameters":{"duration_minutes":30,"content":"stretch"}}
- "Search Google for calisthenics progression exercises" -> {"mode":"action","intent":"web_search","confidence":97,"reply":"Searching Google now.","parameters":{"query":"calisthenics progression exercises","site":"google"}}
- "What is my battery percentage?" -> {"mode":"action","intent":"system_info","confidence":95,"reply":"Checking your battery status.","parameters":{"info_type":"battery"}}
- "Read my C++ course folder and explain it simply" -> {"mode":"action","intent":"analyze_folder","confidence":98,"reply":"Reading the folder now.","parameters":{"path":"Documents\\C++ Course","content":"explain simply","analysis_mode":"explain"}}
- "upload \"C:\\Users\\wassi\\OneDrive\\Desktop\\tp5\\main.cpp\" and explain its code" -> {"mode":"action","intent":"upload_files","confidence":99,"reply":"Reading the file and asking Ollama now.","parameters":{"path":"C:\\Users\\wassi\\OneDrive\\Desktop\\tp5\\main.cpp","content":"explain its code"}}
- "upload the folder \"C:\\Users\\wassi\\OneDrive\\Desktop\\tp5\" and summarize it" -> {"mode":"action","intent":"upload_files","confidence":99,"reply":"Reading the folder and asking Ollama now.","parameters":{"path":"C:\\Users\\wassi\\OneDrive\\Desktop\\tp5","content":"summarize it"}}
- "Take a screenshot of the Opera window" -> {"mode":"action","intent":"screenshot","confidence":98,"reply":"Capturing the Opera window now.","parameters":{"screenshot_scope":"window","target":"opera"}}
"""

def _looks_like_time_query(user_input):
    normalized = (user_input or '').strip().lower()
    return any(keyword in normalized for keyword in ('what time', 'current time', 'time is it', 'the time', 'what date', 'current date', 'today'))


def _direct_time_reply(user_input):
    now = datetime_module.datetime.now()
    normalized = (user_input or '').strip().lower()
    if 'date' in normalized and 'time' not in normalized:
        return {
            'mode': 'chat',
            'intent': 'chat',
            'confidence': 100,
            'reply': now.strftime('Today is %A, %B %d, %Y.'),
            'parameters': {},
        }
    if 'time' in normalized or 'clock' in normalized:
        return {
            'mode': 'chat',
            'intent': 'chat',
            'confidence': 100,
            'reply': f'The current time is {now.strftime("%H:%M:%S")}.',
            'parameters': {},
        }
    return None


def _direct_upload_request(user_input):
    text = (user_input or "").strip()
    if not re.search(r"\bupload\b", text, re.I):
        return None

    quoted_paths = re.findall(r'"([^"]+)"', text)
    if not quoted_paths:
        quoted_paths = re.findall(r"'([^']+)'", text)

    if not quoted_paths:
        return None

    first_path = quoted_paths[0]
    question = text
    marker = f'"{first_path}"'
    marker_index = text.find(marker)
    if marker_index == -1:
        marker = f"'{first_path}'"
        marker_index = text.find(marker)
    if marker_index != -1:
        question = text[marker_index + len(marker):]

    question = re.sub(r"^\s*(and|then|,|-|:)\s*", "", question, flags=re.I).strip()
    if not question:
        question = "summarize the content"

    parameters = {"content": question}
    if len(quoted_paths) == 1:
        parameters["path"] = first_path
    else:
        parameters["paths"] = quoted_paths

    return {
        "mode": "action",
        "intent": "upload_files",
        "confidence": 100,
        "reply": "Reading the requested file content and asking Ollama now.",
        "parameters": parameters,
    }


def _direct_shortcut_request(user_input):
    text = (user_input or "").strip()
    match = re.search(
        r'^\s*set\s+shortcut\s+of\s+["\']([^"\']+)["\']\s+as\s+["\']?([^"\']+?)["\']?\s*$',
        text,
        re.I,
    )
    if not match:
        return None

    target_path = match.group(1).strip()
    alias_name = match.group(2).strip()
    if not target_path or not alias_name:
        return None

    return {
        "mode": "action",
        "intent": "memory_box",
        "confidence": 100,
        "reply": f"Saving shortcut {alias_name}.",
        "parameters": {"target_path": target_path, "alias_name": alias_name},
    }


def _extract_json(text):
    text = (text or "").strip()
    if not text:
        return None

    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, re.S)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            return None
    return None


def analyze_command(user_input):
    direct_reply = _direct_time_reply(user_input)
    if direct_reply is not None:
        return direct_reply

    direct_shortcut = _direct_shortcut_request(user_input)
    if direct_shortcut is not None:
        return direct_shortcut

    direct_upload = _direct_upload_request(user_input)
    if direct_upload is not None:
        return direct_upload

    payload = {
        "model": CONFIG["model_name"],
        "prompt": f"{SYSTEM_PROMPT}\nUser request: {user_input}",
        "format": "json",
        "stream": False,
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=30)
        response.raise_for_status()
        body = response.json()
        structured = _extract_json(body.get("response", ""))

        if not structured:
            fallback_reply = body.get("response", "").strip() or "I could not parse the local model response."
            return {
                "mode": "chat",
                "intent": "chat",
                "confidence": 0,
                "reply": fallback_reply,
                "parameters": {},
            }

        parameters = structured.get("parameters")
        if not isinstance(parameters, dict):
            parameters = {}

        mode = structured.get("mode") or ("chat" if structured.get("intent") == "chat" else "action")
        reply = structured.get("reply") or ""
        intent = structured.get("intent") or "chat"
        confidence = structured.get("confidence", 0)

        if not reply:
            reply = "I am ready."
            if mode == "action":
                reply = "I will handle that now."

        return {
            "mode": mode,
            "intent": intent,
            "confidence": confidence,
            "reply": reply,
            "parameters": parameters,
        }
    except Exception as error:
        return {
            "mode": "chat",
            "intent": "chat",
            "confidence": 0,
            "reply": f"I could not reach the local Qwen model: {error}",
            "parameters": {},
            "error": str(error),
        }
