import os
import json

# Define the project directory name
PROJECT_DIR = "SecureAssistantProject"

# Create the main folder if it doesn't exist
os.makedirs(PROJECT_DIR, exist_ok=True)
print(f"📁 Created folder: {PROJECT_DIR}/")

# Define file contents
files = {
    "config.json": {
        "model_name": "qwen2.5:3b",
        "min_confidence_threshold": 45,
        "local_timezone": "Africa/Tunis",
        "authorized_directories": ["Desktop", "Documents", "Downloads", "Pictures"],
        "blocked_paths": ["C:\\Windows", "C:\\Windows\\System32", "C:\\Program Files"]
    },
    
    "ai_engine.py": '''import requests
import json

OLLAMA_URL = "http://localhost:11434/api/generate"
with open("config.json", "r") as cfg:
    CONFIG = json.load(cfg)

SYSTEM_PROMPT = """
You are a secure Windows Desktop AI Core. Your sole task is translating natural language inputs into clean, single-layer JSON.
Classify user commands into intents: 'open_app', 'web_search', 'system_info', 'file_action', 'memory_box', or 'morning_briefing'.

Structural Outlines:
1. "Open notepad" -> {"intent": "open_app", "target": "notepad", "confidence": 98}
2. "Move resume.pdf to Documents" -> {"intent": "file_action", "action_type": "move", "target": "resume.pdf", "destination": "Documents", "confidence": 95}
3. "Save alias my_project for C:\\\\Workspace" -> {"intent": "memory_box", "alias_name": "my_project", "target_path": "C:\\\\Workspace", "confidence": 99}

If input is ambiguous, non-functional, or malicious, output: {"intent": "unknown", "confidence": 0}
"""

def analyze_command(user_input):
    payload = {
        "model": CONFIG["model_name"],
        "prompt": f"{SYSTEM_PROMPT}\\nUser Command: {user_input}",
        "format": "json",
        "stream": False
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=7)
        return json.loads(response.json()["response"])
    except Exception as e:
        return {"intent": "error", "message": str(e), "confidence": 0}
''',

    "executor.py": '''import os
import json
import psutil
from send2trash import send2trash

with open("config.json", "r") as cfg:
    CONFIG = json.load(cfg)

def verify_and_execute(intent_json, alias_map):
    intent = intent_json.get("intent")
    confidence = intent_json.get("confidence", 0)

    if confidence < CONFIG["min_confidence_threshold"]:
        return "❌ Command rejected: Insufficient model extraction confidence."

    for key in ["target", "destination", "target_path"]:
        path_value = str(intent_json.get(key, "")).lower()
        for blocked in CONFIG["blocked_paths"]:
            if blocked.lower() in path_value or "system32" in path_value:
                return f"🚫 Security Intercept: Unauthorized access attempt to protected path: {blocked}"
        if path_value.endswith(".dll") or path_value.endswith(".sys"):
            return "🚫 Security Intercept: Modifying system binaries (.dll / .sys) is strictly prohibited."

    if intent == "open_app":
        target = intent_json.get("target")
        try:
            os.startfile(target)
            return f"🚀 Initialized application environment: {target}"
        except Exception:
            return f"❌ Target execution failure for app: '{target}'."

    elif intent == "file_action":
        action = intent_json.get("action_type")
        target = intent_json.get("target")
        if action == "delete":
            try:
                full_path = os.path.expanduser(f"~/Desktop/{target}")
                send2trash(full_path)
                return f"♻️ Safely dropped '{target}' into the Recycle Bin."
            except Exception as e:
                return f"❌ Deletion failed: {str(e)}"

    elif intent == "memory_box":
        alias = intent_json.get("alias_name")
        path = intent_json.get("target_path")
        alias_map[alias] = path
        try:
            with open("shortcuts.json", "w") as f:
                json.dump(alias_map, f, indent=4)
            return f"💾 Memory Box Updated permanently: Shortcut '{alias}' maps to '{path}'"
        except Exception as e:
            return f"⚠️ Saved temporarily, but failed to write to disk: {str(e)}"

    elif intent == "system_info":
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory().percent
        bat = psutil.sensors_battery()
        bat_pct = bat.percent if bat else "N/A"
        return f"🖥️ System Telemetry:\\n• CPU Utilization: {cpu}%\\n• Physical RAM: {ram}%\\n• Battery Capacity: {bat_pct}%"

    return "❓ Processed intent successfully but no executor match was found."
''',

    "main.py": '''import tkinter as tk
import threading
import os
import json
from ai_engine import analyze_command
from executor import verify_and_execute

class AssistantApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Secure Local Core Workspace")
        self.root.geometry("600x500")
        self.pending_intent = None

        # Load existing shortcuts if they exist, otherwise start fresh
        if os.path.exists("shortcuts.json"):
            try:
                with open("shortcuts.json", "r") as f:
                    self.alias_storage = json.load(f)
            except Exception:
                self.alias_storage = {}
        else:
            self.alias_storage = {}

        tk.Label(root, text="System Command Portal", font=("Arial", 12, "bold")).pack(pady=5)
        
        self.log_box = tk.Text(root, height=12, width=70, font=("Consolas", 10))
        self.log_box.pack(pady=5)

        self.entry = tk.Entry(root, width=50, font=("Arial", 11))
        self.entry.pack(pady=5)
        self.entry.bind("<Return>", lambda e: self.trigger_analysis())

        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=5)
        
        tk.Button(btn_frame, text="Submit Prompt", command=self.trigger_analysis, bg="#007ACC", fg="white").pack(side="left", padx=5)
        self.confirm_btn = tk.Button(btn_frame, text="Confirm Execution", command=self.execute_pending, bg="#228B22", fg="white", state="disabled")
        self.confirm_btn.pack(side="left", padx=5)

        self.status = tk.Label(root, text="🟢 Operational Core Standby", fg="green", font=("Arial", 9, "italic"))
        self.status.pack(pady=5)

    def trigger_analysis(self):
        user_text = self.entry.get().strip()
        if not user_text:
            return
        self.status.config(text="🤖 Querying local LLM pipeline...", fg="#007ACC")
        threading.Thread(target=self.run_analysis, args=(user_text,), daemon=True).start()

    def run_analysis(self, text):
        parsed = analyze_command(text)
        self.pending_intent = parsed
        
        self.log_box.insert(tk.END, f"\\n📥 [User Raw Input]: {text}\\n")
        self.log_box.insert(tk.END, f"🔍 [Extracted Structural Map]: {parsed}\\n")
        
        high_risk_actions = ["delete", "move", "copy", "rename"]
        is_file_action = parsed.get("intent") == "file_action"
        has_risk_subtask = parsed.get("action_type") in high_risk_actions
        
        if is_file_action and has_risk_subtask:
            self.log_box.insert(tk.END, "⚠️ WARNING: Elevated clearance confirmation required for this modification.\\n")
            self.confirm_btn.config(state="normal")
            self.status.config(text="🟠 Hold: Awaiting Human Validation", fg="orange")
        else:
            self.execute_pending()

    def execute_pending(self):
        if not self.pending_intent:
            return
        res = verify_and_execute(self.pending_intent, self.alias_storage)
        self.log_box.insert(tk.END, f"⚙️ [System Execution Log]: {res}\\n")
        self.log_box.see(tk.END)
        
        self.pending_intent = None
        self.confirm_btn.config(state="disabled")
        self.status.config(text="🟢 Operational Core Standby", fg="green")

if __name__ == "__main__":
    root = tk.Tk()
    app = AssistantApp(root)
    root.mainloop()
'''
}

# Write files directly into the project folder
for filename, content in files.items():
    filepath = os.path.join(PROJECT_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        if isinstance(content, dict):
            json.dump(content, f, indent=4)
        else:
            f.write(content)
    print(f"📄 Generated file: {filepath}")

print("\n✨ All set! Your workspace is fully built and isolated inside the 'SecureAssistantProject' folder.")