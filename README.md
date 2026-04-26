# huarui-cli

一个最小可运行的 Python CLI：
- 兼容 OpenAI SDK 的 `base_url`
- 本地 `skills/` 自动扫描
- 先让模型挑选 skill，再把 skill prompt 注入主 agent
- 主 agent 可以真正执行 shell 命令

## 目录

```bash
mini_shell_skills_cli/
├── app.py
├── requirements.txt
├── .env.example
└── skills/
    └── shell/
        ├── skill.json
        └── prompt.md
```

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```
- 然后编辑你的.env文件


你也可以直接导出环境变量：

```bash
export OPENAI_API_KEY="sk-xxxxxxxx"
export OPENAI_BASE_URL="https://us.novaiapi.com/v1"
export AI_MODEL="gemini-3-pro-preview"
```

## 运行

交互模式：

```bash
python app.py
```

单次执行：

```bash
python app.py "帮我查看当前目录里最大的 5 个文件"
```

指定工作目录：

```bash
python app.py "列出最近 20 行 nginx error log" --workspace /var/log
```

## skill 格式

每个 skill 是一个目录，至少包含两个文件：

### `skill.json`

```json
{
  "name": "shell",
  "description": "linux shell tasks, file inspection, logs, process checks, package checks, and common vps ops"
}
```

### `prompt.md`

这里写该 skill 的附加系统提示，比如：
- 遇到日志问题优先用 `tail`, `grep`, `journalctl`
- 遇到磁盘问题优先用 `df -h`, `du -sh`
- 命令要非交互

## 工作原理

1. CLI 启动后扫描 `skills/`
2. 先调用一次模型做 skill routing
3. 再把命中的 skill prompt 注入 agent
4. agent 必须输出 JSON：
   - `{"action":"shell","command":"...","reason":"..."}`
   - `{"action":"final","content":"..."}`
5. Python 主程序收到 `shell` 就真的执行命令
6. shell 输出再喂回模型，直到得到最终答案

## 重要提醒

这是真执行 shell，所以默认风险很高。最少建议：
- 用普通用户运行，不要直接 root 常驻


## 更新日志

### V1.1
- 新增流式传输
- 重构部分skills调用代码
- 颜色字体区分
- 支持markdown显示
