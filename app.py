#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

MAX_STEPS = 8

SYSTEM_BASE = """You are a CLI agent running on a user's VPS.
You can solve tasks by either:
1. replying to the user directly, or
2. asking the host program to execute one shell command.

You MUST always return valid JSON, with one of these shapes only:

{"action":"final","content":"..."}
{"action":"shell","command":"...","reason":"..."}

Rules:
- Prefer concise shell commands.
- Use non-interactive commands only.
- Do not use editors like vim, nano, less, more, top, htop.
- Avoid commands that wait forever.
- If a task needs multiple commands, ask for them one at a time.
- After receiving shell output, decide the next best action.
- If enough information is available, return action=final.
- When a skill is loaded, follow its extra instructions.
"""

ROUTER_PROMPT = """You are a skill router.
Given a user request and a list of local skills, choose the single best skill.
Return strict JSON only:
{"skill":"<skill_name_or_empty>","reason":"..."}
If no skill is clearly useful, use an empty string for skill.
"""


@dataclass
class Skill:
    name: str
    description: str
    system_prompt: str
    path: Path


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_skills(skills_dir: Path) -> Dict[str, Skill]:
    skills: Dict[str, Skill] = {}
    if not skills_dir.exists():
        return skills
    for item in skills_dir.iterdir():
        if not item.is_dir():
            continue
        manifest = item / "skill.json"
        prompt_file = item / "prompt.md"
        if not manifest.exists() or not prompt_file.exists():
            continue
        data = json.loads(read_text(manifest))
        skill = Skill(
            name=data["name"],
            description=data["description"],
            system_prompt=read_text(prompt_file),
            path=item,
        )
        skills[skill.name] = skill
    return skills


def make_client(api_key: str, base_url: str) -> OpenAI:
    return OpenAI(api_key=api_key, base_url=base_url)


def call_model(client: OpenAI, model: str, messages: List[dict], temperature: float = 0.1) -> str:
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )
    return resp.choices[0].message.content or ""


def safe_json_parse(text: str) -> dict:
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"Model did not return JSON: {text}")
    return json.loads(text[start:end + 1])


def choose_skill(client: OpenAI, model: str, skills: Dict[str, Skill], user_text: str) -> Optional[Skill]:
    if not skills:
        return None
    skill_lines = [f"- {s.name}: {s.description}" for s in skills.values()]
    messages = [
        {"role": "system", "content": ROUTER_PROMPT},
        {"role": "user", "content": "Available skills:\n" + "\n".join(skill_lines)},
        {"role": "user", "content": f"User request:\n{user_text}"},
    ]
    raw = call_model(client, model, messages, temperature=0)
    data = safe_json_parse(raw)
    skill_name = data.get("skill", "")
    return skills.get(skill_name) if skill_name else None


def run_shell(command: str, cwd: Path) -> str:
    proc = subprocess.run(
        command,
        shell=True,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        timeout=60,
        executable="/bin/bash",
    )
    stdout = proc.stdout[-12000:]
    stderr = proc.stderr[-12000:]
    return (
        f"[exit_code]={proc.returncode}\n"
        f"[stdout]\n{stdout}\n"
        f"[stderr]\n{stderr}"
    )


def build_agent_messages(user_text: str, skill: Optional[Skill]) -> List[dict]:
    messages = [{"role": "system", "content": SYSTEM_BASE}]
    if skill:
        messages.append(
            {
                "role": "system",
                "content": f"Loaded local skill: {skill.name}\n{skill.system_prompt}",
            }
        )
    messages.append({"role": "user", "content": user_text})
    return messages


def agent_loop(client: OpenAI, model: str, workspace: Path, user_text: str, skill: Optional[Skill]) -> str:
    messages = build_agent_messages(user_text, skill)
    for step in range(MAX_STEPS):
        raw = call_model(client, model, messages)
        data = safe_json_parse(raw)
        action = data.get("action")

        if action == "final":
            return data.get("content", "")

        if action == "shell":
            command = data.get("command", "").strip()
            reason = data.get("reason", "")
            print(f"\n[step {step + 1}] shell> {command}", file=sys.stderr)
            if reason:
                print(f"reason: {reason}", file=sys.stderr)
            output = run_shell(command, workspace)
            print(output, file=sys.stderr)
            messages.append({"role": "assistant", "content": json.dumps(data, ensure_ascii=False)})
            messages.append({"role": "user", "content": f"Shell result:\n{output}"})
            continue

        raise RuntimeError(f"Unknown action from model: {data}")

    return "达到最大执行步数，已停止。你可以缩小任务范围后再试。"


def interactive_mode(client: OpenAI, model: str, skills: Dict[str, Skill], workspace: Path) -> None:
    print("mini shell skills cli")
    print("Type 'exit' to quit.\n")
    while True:
        try:
            user_text = input("> ").strip()
        except EOFError:
            print()
            break
        if not user_text:
            continue
        if user_text.lower() in {"exit", "quit"}:
            break
        skill = choose_skill(client, model, skills, user_text)
        if skill:
            print(f"[router] loaded skill: {skill.name}", file=sys.stderr)
        reply = agent_loop(client, model, workspace, user_text, skill)
        print(reply)


def main() -> None:
    parser = argparse.ArgumentParser(description="Minimal CLI agent with local skill auto-loading and shell execution.")
    parser.add_argument("task", nargs="?", help="Single-shot task. Omit for interactive mode.")
    parser.add_argument("--model", default=os.getenv("AI_MODEL", "gemini-3-pro-preview"))
    parser.add_argument("--api-key", default=os.getenv("OPENAI_API_KEY"))
    parser.add_argument("--base-url", default=os.getenv("OPENAI_BASE_URL", "https://us.novaiapi.com/v1"))
    parser.add_argument("--skills-dir", default="./skills")
    parser.add_argument("--workspace", default=".")
    args = parser.parse_args()

    if not args.api_key:
        raise SystemExit("Missing API key. Set OPENAI_API_KEY or pass --api-key.")

    client = make_client(args.api_key, args.base_url)
    skills = load_skills(Path(args.skills_dir))
    workspace = Path(args.workspace).resolve()

    if args.task:
        skill = choose_skill(client, args.model, skills, args.task)
        if skill:
            print(f"[router] loaded skill: {skill.name}", file=sys.stderr)
        reply = agent_loop(client, args.model, workspace, args.task, skill)
        print(reply)
        return

    interactive_mode(client, args.model, skills, workspace)


if __name__ == "__main__":
    main()
