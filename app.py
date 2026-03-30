
#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

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


def ask_llm(messages):
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages
        )
        return resp.choices[0].message.content
    except Exception as e:
        return json.dumps({
            "action": "final",
            "content": f"[llm error] {str(e)}"
        })


def loop(query: str):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": query}
    ]

    while True:
        raw = ask_llm(messages)

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
            output = run_shell(cmd)

            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": f"command output:\n{output}"
            })

        elif data.get("action") == "final":
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
