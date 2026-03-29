---
name: shell-helper
description: Help with Linux shell commands, server setup, deployment, process management, logs, nginx, systemd, and common VPS tasks. Invoke when user needs to run shell commands or server-related tasks.
---

# Shell Helper

## Available Scripts
- `execute.py` - Execute shell commands

## Usage
When you need to:
- Run Linux shell commands
- Check system status
- Manage processes
- Configure servers
- Troubleshoot server issues

## How to Call
Use the following format to call the script:
```
CALL_SCRIPT: execute.py <command>
```

## Examples
- List files: `CALL_SCRIPT: execute.py ls -la`
- Check system status: `CALL_SCRIPT: execute.py uptime`
- View processes: `CALL_SCRIPT: execute.py ps aux | grep nginx`
- Read logs: `CALL_SCRIPT: execute.py tail -f /var/log/syslog`

## Behavior
- Provide commands in a copy-paste friendly way.
- Assume Ubuntu unless user says otherwise.
- Prefer safe commands first.
- Always use the CALL_SCRIPT format for actual command execution.

