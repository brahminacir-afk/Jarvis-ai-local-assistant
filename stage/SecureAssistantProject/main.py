import json
import os
import threading
import tkinter as tk
from tkinter import scrolledtext
from pathlib import Path

from ai_engine import analyze_command
from executor import HIGH_RISK_INTENTS, set_notification_callback, verify_and_execute
from voice_input import listen_once


BASE_DIR = Path(__file__).resolve().parent
SHORTCUTS_PATH = BASE_DIR / "shortcuts.json"


class AssistantApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Jarvis | Secure Local Assistant")
        self.root.geometry("920x700")
        self.root.minsize(820, 620)
        self.root.configure(bg="#0B1220")
        self.pending_intent = None
        self.pending_reply = ""
        self.is_busy = False
        self.guide_window = None

        if SHORTCUTS_PATH.exists():
            try:
                with open(SHORTCUTS_PATH, "r", encoding="utf-8") as handle:
                    self.alias_storage = json.load(handle)
            except Exception:
                self.alias_storage = {}
        else:
            self.alias_storage = {}

        set_notification_callback(self.append_log)

        # Main dashboard: a simple visual hierarchy makes normal and sensitive
        # actions easy to distinguish at a glance.
        header = tk.Frame(root, bg="#111C31", padx=26, pady=18)
        header.pack(fill="x")
        tk.Label(
            header, text="JARVIS", bg="#111C31", fg="#F8FAFC",
            font=("Segoe UI", 22, "bold"),
        ).pack(anchor="w")
        tk.Label(
            header, text="Private local assistant - Your requests stay on this computer",
            bg="#111C31", fg="#94A3B8", font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(2, 0))

        content = tk.Frame(root, bg="#0B1220", padx=20, pady=18)
        content.pack(fill="both", expand=True)

        activity_frame = tk.LabelFrame(
            content, text="  ACTIVITY  ", bg="#111C31", fg="#93C5FD",
            font=("Segoe UI", 10, "bold"), bd=1, relief="solid", padx=12, pady=10,
        )
        activity_frame.pack(fill="both", expand=True)
        self.log_box = scrolledtext.ScrolledText(
            activity_frame, height=15, font=("Consolas", 10), wrap="word",
            bg="#0F172A", fg="#E2E8F0", insertbackground="white", relief="flat",
            padx=12, pady=10,
        )
        self.log_box.pack(fill="both", expand=True)

        command_frame = tk.LabelFrame(
            content, text="  YOUR COMMAND  ", bg="#111C31", fg="#93C5FD",
            font=("Segoe UI", 10, "bold"), bd=1, relief="solid", padx=12, pady=10,
        )
        command_frame.pack(fill="x", pady=(14, 0))
        self.entry = tk.Entry(
            command_frame, font=("Segoe UI", 12), bg="#0F172A", fg="#F8FAFC",
            insertbackground="white", relief="flat",
        )
        self.entry.pack(fill="x", ipady=10)
        self.entry.bind("<Return>", lambda event: self.trigger_analysis())

        button_row = tk.Frame(content, bg="#0B1220")
        button_row.pack(fill="x", pady=12)

        self.submit_btn = tk.Button(
            button_row,
            text="Send command",
            command=self.trigger_analysis,
            bg="#2563EB",
            fg="white",
            activebackground="#1D4ED8",
            activeforeground="white",
            relief="flat", cursor="hand2", font=("Segoe UI", 10, "bold"),
            width=18, pady=9,
        )
        self.submit_btn.pack(side="left", padx=(0, 8))

        self.voice_btn = tk.Button(
            button_row,
            text="Voice command",
            command=self.trigger_voice_input,
            bg="#7C3AED",
            fg="white",
            activebackground="#6D28D9",
            activeforeground="white",
            relief="flat", cursor="hand2", font=("Segoe UI", 10, "bold"),
            width=18, pady=9,
        )
        self.voice_btn.pack(side="left", padx=8)

        self.confirm_btn = tk.Button(
            button_row,
            text="Confirm sensitive action",
            command=self.execute_pending,
            bg="#059669",
            fg="white",
            state="disabled",
            activebackground="#047857",
            activeforeground="white",
            disabledforeground="#94A3B8",
            relief="flat", cursor="hand2", font=("Segoe UI", 10, "bold"),
            width=24, pady=9,
        )
        self.confirm_btn.pack(side="left", padx=8)

        self.guide_btn = tk.Button(
            button_row,
            text="?  Help & examples",
            command=self.open_guide_lines,
            bg="#334155",
            fg="white",
            activebackground="#475569",
            activeforeground="white",
            relief="flat", cursor="hand2", font=("Segoe UI", 10, "bold"),
            width=18, pady=9,
        )
        self.guide_btn.pack(side="right")

        prompt_frame = tk.LabelFrame(
            content, text="  QUICK ACTIONS  ", bg="#111C31", fg="#93C5FD",
            font=("Segoe UI", 10, "bold"), bd=1, relief="solid", padx=12, pady=10,
        )
        prompt_frame.pack(fill="x")

        self.prompt_templates = [
            ("Create Folder", 'create a folder named "Projects" in "C:\\Users\\wassi\\Documents"'),
            ("Open Folder", 'open my "Downloads" folder'),
            ("List Folder", 'list the files in my Downloads folder'),
            ("Search Files", 'search my Documents for notes'),
            ("Set Alarm", 'set an alarm for 8:00 PM'),
            ("Set Reminder", 'remind me in 30 minutes to stretch'),
            ("Study Folder", 'analyze the folder "Documents\\C++ Course" and explain it simply'),
            ("Upload File", 'upload "C:\\Users\\wassi\\OneDrive\\Desktop\\tp5\\main.cpp" and explain its code'),
            ("Upload Folder", 'upload the folder "C:\\Users\\wassi\\OneDrive\\Desktop\\tp5" and summarize the content'),
            ("Open App", 'open Notepad'),
            ("Take Note", 'take a note: review the C++ assignment'),
        ]

        for index, (label, prompt_text) in enumerate(self.prompt_templates):
            button = tk.Button(
                prompt_frame,
                text=label,
                command=lambda value=prompt_text: self.load_prompt(value),
                bg="#1E293B",
                fg="#E2E8F0",
                activebackground="#334155",
                activeforeground="white",
                relief="flat", cursor="hand2", font=("Segoe UI", 9),
                width=18, pady=6,
            )
            button.grid(row=index // 4, column=index % 4, padx=4, pady=4, sticky="ew")
        for column in range(4):
            prompt_frame.grid_columnconfigure(column, weight=1)

        self.status = tk.Label(
            root, text="Ready - local mode enabled", bg="#111C31", fg="#86EFAC",
            font=("Segoe UI", 10), anchor="w", padx=22, pady=10,
        )
        self.status.pack(fill="x", side="bottom")

    def close_guide_lines(self):
        if self.guide_window and self.guide_window.winfo_exists():
            self.guide_window.destroy()
        self.guide_window = None

    def open_guide_lines(self):
        if self.guide_window and self.guide_window.winfo_exists():
            self.guide_window.deiconify()
            self.guide_window.lift()
            self.guide_window.focus_force()
            self.set_status("Guide open. Pick an example or type your own command.", "#6D28D9")
            return

        window = tk.Toplevel(self.root)
        self.guide_window = window
        window.title("guide_lines")
        window.geometry("980x700")
        window.configure(bg="#0F172A")
        window.protocol("WM_DELETE_WINDOW", self.close_guide_lines)
        self.set_status("Guide open. Pick an example or type your own command.", "#6D28D9")

        header = tk.Frame(window, bg="#111827", padx=18, pady=14)
        header.pack(fill="x")

        tk.Label(
            header,
            text="guide_lines",
            font=("Segoe UI", 22, "bold"),
            bg="#111827",
            fg="white",
        ).pack(anchor="w")
        tk.Label(
            header,
            text="A quick tour of what Jarvis can do and how to talk to it.",
            font=("Segoe UI", 10),
            bg="#111827",
            fg="#CBD5E1",
        ).pack(anchor="w", pady=(4, 0))

        body = tk.Frame(window, bg="#0F172A")
        body.pack(fill="both", expand=True, padx=14, pady=14)
        body.grid_columnconfigure(0, weight=2)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        guide_text = scrolledtext.ScrolledText(
            body,
            wrap="word",
            font=("Consolas", 10),
            bg="#111827",
            fg="#E5E7EB",
            insertbackground="white",
            relief="flat",
            padx=12,
            pady=12,
        )
        guide_text.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        guide_text.tag_configure("title", font=("Segoe UI", 14, "bold"), foreground="#F8FAFC")
        guide_text.tag_configure("heading", font=("Segoe UI", 11, "bold"), foreground="#93C5FD")
        guide_text.tag_configure("accent", foreground="#A78BFA")
        guide_text.tag_configure("bullet", lmargin1=18, lmargin2=34, foreground="#E5E7EB")
        guide_text.tag_configure("mono", font=("Consolas", 10), foreground="#FDE68A")

        lines = [
            ("Welcome", "title"),
            (
                "Jarvis is your local Windows assistant. It can open apps, manage files, summarize folders, "
                "take screenshots of specific windows, set alarms, create reminders, and answer simple system questions.\n\n",
                None,
            ),
            ("How to talk to Jarvis", "heading"),
            ("• Say what you want in plain English.\n", "bullet"),
            ("• Name folders exactly when you can, like ", "bullet"),
            ("Documents\\C++ Course", "mono"),
            (" or ", "bullet"),
            ("C:\\Users\\wassi\\OneDrive\\Desktop\\word", "mono"),
            (".\n", "bullet"),
            ("• For window screenshots, say the app name plus ", "bullet"),
            ("window", "mono"),
            (" like ", "bullet"),
            ("Opera window", "mono"),
            (".\n", "bullet"),
            ("• For study help, ask for ", "bullet"),
            ("summarize", "mono"),
            (", ", "bullet"),
            ("explain simply", "mono"),
            (", or ", "bullet"),
            ("give exercises", "mono"),
            (".\n\n", "bullet"),
            ("â€¢ To ask about exact files, say ", "bullet"),
            ("upload \"C:\\Users\\wassi\\OneDrive\\Desktop\\tp5\\main.cpp\" and explain its code", "mono"),
            (".\n\n", "bullet"),
            ("What Jarvis can do", "heading"),
            ("• Open installed applications by name.\n", "bullet"),
            ("• Read common study files: text, code, Word, PDF, spreadsheets, and more.\n", "bullet"),
            ("• Search, create, rename, move, copy, and delete files and folders safely.\n", "bullet"),
            ("• Take screenshots of the whole screen, the active window, or one named app window.\n", "bullet"),
            ("• Set alarms and reminders with local Windows notifications.\n", "bullet"),
            ("• Save notes and recall shortcuts for your own workflow.\n\n", "bullet"),
            ("Best examples", "heading"),
            ("• ", "bullet"),
            ("open the app \"HandBrake\"\n", "mono"),
            ("• ", "bullet"),
            ("analyze the folder \"C:\\Users\\wassi\\OneDrive\\Desktop\\word\" and explain it simply\n", "mono"),
            ("• ", "bullet"),
            ("take a screenshot of the Opera window\n", "mono"),
            ("• ", "bullet"),
            ("set an alarm for 15:44\n", "mono"),
            ("• ", "bullet"),
            ("remind me in 20 minutes to drink water\n", "mono"),
            ("• ", "bullet"),
            ("open the latest file in Downloads\n\n", "mono"),
            ("Safety and behavior", "heading"),
            ("• Jarvis asks for confirmation before risky file actions.\n", "bullet"),
            ("• It only works inside safe user folders and your project folder.\n", "bullet"),
            ("• If a folder contains mixed document types, Jarvis samples the readable ones and summarizes them.\n", "bullet"),
            ("• If a window is minimized or hidden, window screenshots may be limited.\n\n", "bullet"),
            ("Tip", "heading"),
            ("Use the guide_lines button any time you want a refresher. You can also click the examples on the right to load a command instantly.\n", "bullet"),
        ]

        for text, tag in lines:
            if tag is None:
                guide_text.insert(tk.END, text)
            else:
                guide_text.insert(tk.END, text, tag)

        guide_text.configure(state="disabled")

        side = tk.Frame(body, bg="#0F172A")
        side.grid(row=0, column=1, sticky="nsew")

        examples_frame = tk.LabelFrame(
            side,
            text="Try these",
            font=("Segoe UI", 10, "bold"),
            bg="#111827",
            fg="#E5E7EB",
            bd=1,
            relief="solid",
            padx=10,
            pady=10,
        )
        examples_frame.pack(fill="both", expand=False)

        self.guide_examples = [
            ("Open App", 'open the app "HandBrake"'),
            ("Analyze Folder", 'analyze the folder "C:\\Users\\wassi\\OneDrive\\Desktop\\word" and explain it simply'),
            ("Upload File", 'upload "C:\\Users\\wassi\\OneDrive\\Desktop\\tp5\\main.cpp" and explain its code'),
            ("Upload Folder", 'upload the folder "C:\\Users\\wassi\\OneDrive\\Desktop\\tp5" and summarize it'),
            ("Window Shot", "take a screenshot of the Opera window"),
            ("Alarm", "set an alarm for 15:44"),
            ("Reminder", "remind me in 20 minutes to drink water"),
            ("Study Folder", 'analyze the folder "Documents\\C++ Course" and give exercises'),
        ]

        for label, prompt_text in self.guide_examples:
            tk.Button(
                examples_frame,
                text=label,
                command=lambda value=prompt_text: self.load_prompt(value),
                width=26,
                bg="#1D4ED8",
                fg="white",
                activebackground="#2563EB",
                relief="flat",
            ).pack(fill="x", pady=4)

        summary_frame = tk.LabelFrame(
            side,
            text="Jarvis snapshot",
            font=("Segoe UI", 10, "bold"),
            bg="#111827",
            fg="#E5E7EB",
            bd=1,
            relief="solid",
            padx=10,
            pady=10,
        )
        summary_frame.pack(fill="both", expand=True, pady=(12, 0))

        summary_text = (
            "Jarvis is designed to work like a local cockpit for your PC.\n\n"
            "It can:\n"
            "- read course folders and explain them simply\n"
            "- open almost any installed app by name\n"
            "- capture specific app windows\n"
            "- handle alarms, reminders, notes, and file actions\n"
            "- keep everything local and ask before risky actions\n"
        )
        tk.Label(
            summary_frame,
            text=summary_text,
            justify="left",
            bg="#111827",
            fg="#E5E7EB",
            anchor="nw",
            font=("Segoe UI", 10),
        ).pack(fill="both", expand=True)

    def load_prompt(self, prompt_text):
        self.entry.delete(0, tk.END)
        self.entry.insert(0, prompt_text)
        self.entry.focus_set()
        self.set_status("Prompt loaded. Edit it if you want, then submit.", "#007ACC")

    def set_status(self, text, color="green"):
        self.root.after(0, lambda: self.status.config(text=text, fg=color))

    def append_log(self, text):
        def _append():
            self.log_box.insert(tk.END, f"{text}\n")
            self.log_box.see(tk.END)

        self.root.after(0, _append)

    def set_confirm_state(self, enabled):
        state = "normal" if enabled else "disabled"
        self.root.after(0, lambda: self.confirm_btn.config(state=state))

    def set_busy(self, busy):
        self.is_busy = busy
        state = "disabled" if busy else "normal"
        self.root.after(0, lambda: self.submit_btn.config(state=state))
        self.root.after(0, lambda: self.voice_btn.config(state=state))

    def trigger_analysis(self):
        user_text = self.entry.get().strip()
        if not user_text or self.is_busy:
            return

        self.set_busy(True)
        self.set_confirm_state(False)
        self.set_status("Querying local Qwen model...", "#007ACC")
        self.append_log(f"[User Raw Input]: {user_text}")

        thread = threading.Thread(target=self.run_analysis, args=(user_text,), daemon=True)
        thread.start()

    def trigger_voice_input(self):
        """Listen locally, then send the transcription through the normal safe flow."""
        if self.is_busy:
            return

        self.set_busy(True)
        self.set_confirm_state(False)
        self.set_status("Listening locally... Speak your command.", "#6D28D9")
        self.append_log("[Voice Input]: Listening through the local Windows speech engine.")
        threading.Thread(target=self.run_voice_input, daemon=True).start()

    def run_voice_input(self):
        try:
            user_text = listen_once()
            self.append_log(f"[Voice Input]: {user_text}")
            self.root.after(0, lambda: self._show_voice_text(user_text))
            self.set_status("Querying local Qwen model...", "#007ACC")
            self.run_analysis(user_text)
        except Exception as error:
            self.append_log(f"[Voice Input Error]: {error}")
            self.set_status("Voice input failed. Check the microphone and try again.", "#B91C1C")
            self.set_busy(False)

    def _show_voice_text(self, user_text):
        self.entry.delete(0, tk.END)
        self.entry.insert(0, user_text)

    def run_analysis(self, text):
        try:
            parsed = analyze_command(text)
            self.pending_intent = parsed
            self.pending_reply = parsed.get("reply", "")

            self.append_log(f"[Extracted Structural Map]: {parsed}")
            if self.pending_reply:
                self.append_log(f"[Assistant Reply]: {self.pending_reply}")

            if parsed.get("mode") == "blocked" or parsed.get("intent") == "chat":
                self.pending_intent = None
                if self.pending_reply:
                    self.append_log(f"[System Execution Log]: {self.pending_reply}")
                self.set_status("Operational core standby", "green")
                return

            intent_name = parsed.get("intent")
            action_type = str(parsed.get("parameters", {}).get("action_type", "")).strip().lower()
            if intent_name in HIGH_RISK_INTENTS or (
                intent_name == "file_action"
                and action_type in {"delete", "move", "rename", "delete_folder", "move_folder", "rename_folder", "remove_folder"}
            ):
                self.append_log("[System Execution Log]: Confirmation required before this file action.")
                self.set_confirm_state(True)
                self.set_status("Hold: awaiting human validation", "orange")
                return

            result = verify_and_execute(parsed, self.alias_storage)
            self.append_log(f"[System Execution Log]: {result}")
            self.pending_intent = None
            self.set_status("Operational core standby", "green")
        finally:
            self.set_busy(False)
            if self.pending_intent is None:
                self.set_confirm_state(False)
            self.root.after(0, lambda: self.entry.delete(0, tk.END))

    def execute_pending(self):
        if not self.pending_intent:
            return

        parsed = self.pending_intent
        self.set_confirm_state(False)
        self.set_status("Executing confirmed request...", "#007ACC")
        self.set_busy(True)

        def _run():
            try:
                result = verify_and_execute(parsed, self.alias_storage)
                self.append_log(f"[System Execution Log]: {result}")
                self.pending_intent = None
                self.set_status("Operational core standby", "green")
            finally:
                self.set_busy(False)
                self.root.after(0, lambda: self.entry.delete(0, tk.END))

        threading.Thread(target=_run, daemon=True).start()


if __name__ == "__main__":
    root = tk.Tk()
    app = AssistantApp(root)
    root.mainloop()
