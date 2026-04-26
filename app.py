
#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from dotenv import load_dotenv
from openai import OpenAI

try:
    from rich.console import Console
    from rich.live import Live
    from rich.markdown import Markdown
    RICH_IMPORT_ERROR = None
except ImportError:
    Console = None
    Live = None
    Markdown = None
    RICH_IMPORT_ERROR = "Rich is not installed. Run: pip install -r requirements.txt"

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL")
)

MODEL = os.getenv("AI_MODEL", "gpt-4o-mini")
BASE_DIR = Path(__file__).resolve().parent
SKILLS_DIR = BASE_DIR / "skills"

COLOR_ENABLED = sys.stdout.isatty() and "NO_COLOR" not in os.environ
RESET = "\033[0m"
BOLD = "\033[1m"
ASSISTANT_COLOR = "\033[95m"
SHELL_COLOR = "\033[96m"
console = Console() if Console else None

BASE_SYSTEM_PROMPT = """
You are an agent that can execute shell commands.

You must ONLY respond in JSON:

1. Execute command:
{"action":"shell","command":"...","reason":"..."}

2. Final answer:
{"action":"final","content":"..."}
"""


def load_skills():
    skills = []
    if not SKILLS_DIR.exists():
        return skills

    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir():
            continue

        meta_path = skill_dir / "skill.json"
        prompt_path = skill_dir / "prompt.md"
        if not meta_path.exists() or not prompt_path.exists():
            continue

        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            prompt = prompt_path.read_text(encoding="utf-8").strip()
        except Exception:
            continue

        name = meta.get("name", skill_dir.name)
        description = meta.get("description", "")
        skills.append({
            "name": name,
            "description": description,
            "prompt": prompt,
        })

    return skills


def build_system_prompt():
    skills = load_skills()
    if not skills:
        return BASE_SYSTEM_PROMPT

    sections = [
        BASE_SYSTEM_PROMPT.strip(),
        "",
        "Available local skills:",
        "Use the relevant skill instructions when the user's request matches a skill.",
    ]

    for skill in skills:
        sections.extend([
            "",
            f"## Skill: {skill['name']}",
            f"Description: {skill['description']}",
            skill["prompt"],
        ])

    return "\n".join(sections)


def run_shell(cmd: str):
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.stdout + result.stderr
    except Exception as e:
        return f"[shell error] {str(e)}"


def colorize(text: str, color: str):
    if not COLOR_ENABLED:
        return text
    return f"{color}{text}{RESET}"


def role_line(role: str, text: str):
    colors = {
        "assistant": ASSISTANT_COLOR,
        "shell": SHELL_COLOR,
    }
    color = colors.get(role, "")
    label = colorize(f"[{role}]", f"{BOLD}{color}") if color else f"[{role}]"
    body = colorize(text, color) if color else text
    return f"{label} {body}"


def render_markdown(text: str):
    if console and Markdown:
        console.print(Markdown(text or ""))
        return
    if RICH_IMPORT_ERROR:
        print(f"[warning] {RICH_IMPORT_ERROR}", file=sys.stderr)
    print(text)


def extract_chunk_text(chunk) -> str:
    choices = getattr(chunk, "choices", None) or []
    if not choices:
        return ""

    delta = getattr(choices[0], "delta", None)
    if delta is None:
        return ""

    content = getattr(delta, "content", None)
    if isinstance(content, str):
        return content
    return ""


class FinalMarkdownStreamer:
    def __init__(self):
        self.raw = ""
        self.content = ""
        self.printed = False
        self.is_final = False
        self.content_started = False
        self.content_done = False
        self._escape = False
        self._unicode_mode = False
        self._unicode_buf = ""
        self._live = None

    def feed(self, text: str):
        if not text:
            return

        self.raw += text

        if not self.is_final:
            self.is_final = bool(re.search(r'"action"\s*:\s*"final"', self.raw))

        if not self.is_final or self.content_done:
            return

        if not self.content_started:
            match = re.search(r'"content"\s*:\s*"', self.raw)
            if not match:
                return
            self.content_started = True
            content_fragment = self.raw[match.end():]
            self._start_live()
        else:
            content_fragment = text

        self._emit_content(content_fragment)

    def finish(self):
        if self._live:
            self._live.stop()
            self._live = None

    def _start_live(self):
        if console and Markdown and Live:
            self._live = Live(
                Markdown(""),
                console=console,
                refresh_per_second=12,
                transient=False,
            )
            self._live.start()

    def _update_output(self):
        self.printed = True
        if self._live:
            self._live.update(Markdown(self.content or " "))
            return
        print(self.content, end="\r", flush=True)

    def _append_content(self, text: str):
        if not text:
            return
        self.content += text
        self._update_output()

    def _emit_content(self, text: str):
        i = 0
        while i < len(text):
            ch = text[i]

            if self._unicode_mode:
                if ch.lower() in "0123456789abcdef":
                    self._unicode_buf += ch
                    if len(self._unicode_buf) == 4:
                        self._append_content(chr(int(self._unicode_buf, 16)))
                        self._unicode_mode = False
                        self._unicode_buf = ""
                else:
                    self._append_content("\\u" + self._unicode_buf + ch)
                    self._unicode_mode = False
                    self._unicode_buf = ""
                i += 1
                continue

            if self._escape:
                mapping = {
                    '"': '"',
                    "\\": "\\",
                    "/": "/",
                    "b": "\b",
                    "f": "\f",
                    "n": "\n",
                    "r": "\r",
                    "t": "\t",
                }
                if ch == "u":
                    self._unicode_mode = True
                    self._unicode_buf = ""
                else:
                    self._append_content(mapping.get(ch, ch))
                self._escape = False
                i += 1
                continue

            if ch == "\\":
                self._escape = True
                i += 1
                continue

            if ch == '"':
                self.content_done = True
                self.finish()
                return

            self._append_content(ch)
            i += 1


def ask_llm(messages):
    try:
        stream = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            stream=True
        )

        printer = FinalMarkdownStreamer()
        for chunk in stream:
            delta = extract_chunk_text(chunk)
            if not delta:
                continue
            printer.feed(delta)

        printer.finish()
        return printer.raw, printer.printed
    except Exception as e:
        return json.dumps({
            "action": "final",
            "content": f"[llm error] {str(e)}"
        }), False


def loop(query: str):
    messages = [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": query}
    ]

    while True:
        raw, already_printed = ask_llm(messages)

        try:
            data = json.loads(raw)
        except Exception:
            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": "Output MUST be JSON. Fix format."
            })
            continue

        if data.get("action") == "shell":
            cmd = data.get("command")
            reason = data.get("reason", "")
            if reason:
                print(role_line("assistant", reason))
            print(role_line("shell", cmd))
            output = run_shell(cmd)
            print(output, end="" if output.endswith("\n") else "\n")

            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": f"command output:\n{output}"
            })

        elif data.get("action") == "final":
            if not already_printed:
                render_markdown(data.get("content"))
            break

        else:
            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": "Invalid action. Use shell or final."
            })


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="?", help="user query")
    args = parser.parse_args()

    if args.query:
        loop(args.query)
    else:
        # REPL 模式：永不退出
        print("Shell AI CLI (type 'exit' to quit)")
        while True:
            try:
                q = input("> ")
                if q.strip() in ["exit", "quit"]:
                    break
                if not q.strip():
                    continue
                loop(q)
            except KeyboardInterrupt:
                print("\n[interrupted]")
                continue
            except Exception as e:
                print(f"[fatal handled] {e}")
                continue


if __name__ == "__main__":
    main()
