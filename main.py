import os
import re
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from dotenv import load_dotenv
from openai import OpenAI  # 继续使用你提供的 OpenAI 客户端


load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-5")
SKILLS_DIR = Path(os.getenv("SKILLS_DIR", "./skills")).resolve()

BASE_URL = os.getenv("OPENAI_BASE_URL", "https://us.novaiapi.com/v1")  # 默认设置为你的自定义 API URL

# 使用自定义的 OpenAI 客户端
client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url=BASE_URL  # 使用自定义的 base_url
)

# 剩下的代码保持不变...
def parse_skill_md(skill_md_path: Path) -> Dict[str, Any]:
    text = skill_md_path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not match:
        raise ValueError(f"SKILL.md missing YAML frontmatter: {skill_md_path}")

    frontmatter = yaml.safe_load(match.group(1)) or {}
    body = match.group(2).strip()

    return {
        "name": frontmatter.get("name", skill_md_path.parent.name),
        "description": frontmatter.get("description", ""),
        "body": body,
        "path": skill_md_path.parent,
    }


def load_skills(skills_dir: Path) -> List[Dict[str, Any]]:
    skills = []
    if not skills_dir.exists():
        return skills

    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            try:
                skills.append(parse_skill_md(skill_md))
            except Exception as e:
                print(f"[WARN] Failed to load skill {skill_dir.name}: {e}")
    return skills


def choose_skill(user_input: str, skills: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not skills:
        return None

    skill_catalog = [
        {
            "name": s["name"],
            "description": s["description"],
        }
        for s in skills
    ]

    prompt = f"""
You are a skill router.

User request:
{user_input}

Available skills:
{json.dumps(skill_catalog, ensure_ascii=False, indent=2)}

Return JSON only:
{{
  "skill_name": "<best skill name or empty string>",
  "reason": "<short reason>",
  "confidence": 0.0
}}

Choose a skill only if it is clearly relevant.
""".strip()

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.choices[0].message.content.strip()  # 修改此处以适应你自定义 API 的响应格式

    try:
        data = json.loads(text)
        skill_name = data.get("skill_name", "").strip()
        confidence = float(data.get("confidence", 0.0))
    except Exception:
        return None

    if not skill_name or confidence < 0.45:
        return None

    for s in skills:
        if s["name"] == skill_name:
            return s
    return None


def extract_script_hints(skill_body: str) -> List[str]:
    scripts = re.findall(r"scripts/([A-Za-z0-9_\-./]+)", skill_body)
    return sorted(set(scripts))


def run_local_script(skill: Dict[str, Any], script_rel_path: str, args: List[str]) -> str:
    script_path = skill["path"] / "scripts" / Path(script_rel_path).name
    if not script_path.exists():
        return f"[ERROR] Script not found: {script_path}"

    cmd = ["python3", str(script_path)] + args

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(skill["path"]),
        )
        output = result.stdout.strip()
        err = result.stderr.strip()

        if result.returncode != 0:
            return f"[SCRIPT ERROR]\n{err or output}"
        return output or "[SCRIPT OK] No output."
    except Exception as e:
        return f"[ERROR] Failed to run script: {e}"


def parse_model_output(text: str) -> Optional[Dict[str, Any]]:
    try:
        # 提取 JSON（防止模型加解释）
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        return json.loads(match.group(0))
    except Exception:
        return None


def chat_with_optional_skill(user_input: str, history: List[Dict[str, str]], skills: List[Dict[str, Any]]) -> str:
    chosen_skill = choose_skill(user_input, skills)

    if chosen_skill:
        script_hints = extract_script_hints(chosen_skill["body"])

        system_prompt = f"""
You are a CLI agent with tool usage capability.

Skill:
{chosen_skill["name"]}

Description:
{chosen_skill["description"]}

Instructions:
{chosen_skill["body"]}

Available scripts:
{json.dumps(script_hints)}

You MUST respond in JSON format ONLY:

{{
  "action": "call_script" or "final_answer",
  "script": "<script name if calling>",
  "args": ["arg1", "arg2"],
  "answer": "<final answer if not calling>"
}}

Rules:
- If a script can solve the task → action = call_script
- Otherwise → action = final_answer
- NEVER output anything outside JSON
""".strip()
    else:
        system_prompt = """
You are a CLI assistant.

Respond in JSON:

{
  "action": "final_answer",
  "answer": "..."
}
"""

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_input})

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
    )

    text = response.choices[0].message.content.strip()

    data = parse_model_output(text)

    if not data:
        return text  # fallback

    #  如果要调用脚本
    if data.get("action") == "call_script" and chosen_skill:
        script_name = data.get("script")
        args = data.get("args", [])

        script_result = run_local_script(chosen_skill, script_name, args)

        #  二次调用生成最终答案
        followup_messages = messages + [
            {"role": "assistant", "content": text},
            {
                "role": "user",
                "content": f"Script result:\n{script_result}\n\nNow return final answer in JSON.",
            },
        ]

        response2 = client.chat.completions.create(
            model=MODEL,
            messages=followup_messages,
        )

        text2 = response2.choices[0].message.content.strip()
        data2 = parse_model_output(text2)

        if data2 and data2.get("answer"):
            return data2["answer"]

        return text2

    # 🧾 普通回答
    return data.get("answer", text)


def main():
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is missing in .env")

    skills = load_skills(SKILLS_DIR)
    print(f"[INFO] Loaded {len(skills)} skills from {SKILLS_DIR}")
    print("Local Agent CLI. Type 'exit' to quit.\n")

    history: List[Dict[str, str]] = []

    while True:
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            print("Bye.")
            break

        try:
            answer = chat_with_optional_skill(user_input, history, skills)
            print(f"\n{answer}\n")
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": answer})
        except Exception as e:
            print(f"[ERROR] {e}")


if __name__ == "__main__":
    main()
