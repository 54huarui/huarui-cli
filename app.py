
#!/usr/bin/env python3
import argparse
import json
import os
import subprocess

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL")
)

MODEL = os.getenv("AI_MODEL", "gpt-4o-mini")

SYSTEM_PROMPT = """
You are an agent that can execute shell commands.

You must ONLY respond in JSON:

1. Execute command:
{"action":"shell","command":"...","reason":"..."}

2. Final answer:
{"action":"final","content":"..."}
"""


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


class FinalContentStreamer:
    def __init__(self):
        self.raw = ""
        self.printed = False
        self.is_final = False
        self.content_started = False
        self.content_done = False

        self._content_key = '"content":"'
        self._escape = False
        self._unicode_mode = False
        self._unicode_buf = ""

    def feed(self, text: str):
        if not text:
            return

        self.raw += text

        if not self.is_final and '"action":"final"' in self.raw:
            self.is_final = True

        if not self.is_final or self.content_done:
            return

        if not self.content_started:
            idx = self.raw.find(self._content_key)
            if idx == -1:
                return
            self.content_started = True
            start = idx + len(self._content_key)
            content_fragment = self.raw[start:]
        else:
            content_fragment = text

        self._emit_content(content_fragment)

    def _emit_content(self, text: str):
        i = 0
        while i < len(text):
            ch = text[i]

            if self._unicode_mode:
                if ch.lower() in "0123456789abcdef":
                    self._unicode_buf += ch
                    if len(self._unicode_buf) == 4:
                        self._print(chr(int(self._unicode_buf, 16)))
                        self._unicode_mode = False
                        self._unicode_buf = ""
                else:
                    self._print("\\u" + self._unicode_buf + ch)
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
                    self._print(mapping.get(ch, ch))
                self._escape = False
                i += 1
                continue

            if ch == "\\":
                self._escape = True
                i += 1
                continue

            if ch == '"':
                self.content_done = True
                if self.printed:
                    print(flush=True)
                return

            self._print(ch)
            i += 1

    def _print(self, text: str):
        if not text:
            return
        self.printed = True
        print(text, end="", flush=True)


def ask_llm(messages):
    try:
        stream = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            stream=True
        )

        printer = FinalContentStreamer()
        for chunk in stream:
            delta = extract_chunk_text(chunk)
            if not delta:
                continue
            printer.feed(delta)

        return printer.raw, printer.printed
    except Exception as e:
        return json.dumps({
            "action": "final",
            "content": f"[llm error] {str(e)}"
        }), False


def loop(query: str):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
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
                print(f"[assistant] {reason}")
            print(f"[shell] {cmd}")
            output = run_shell(cmd)
            print(output, end="" if output.endswith("\n") else "\n")

            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": f"command output:\n{output}"
            })

        elif data.get("action") == "final":
            if not already_printed:
                print(data.get("content"))
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
