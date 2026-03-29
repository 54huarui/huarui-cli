import subprocess
import sys
import platform

def execute_shell(command):
    if not command:
        return "[ERROR] No command provided. Usage: execute.py <command>"

    try:
        # 对于 Windows，使用 PowerShell
        if platform.system() == "Windows":
            cmd = ["powershell.exe", "-Command", command]
        else:
            # 对于 Linux/macOS，使用 bash
            cmd = ["bash", "-c", command]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            shell=False
        )
        
        output = result.stdout.strip()
        error = result.stderr.strip()

        if result.returncode != 0:
            return f"[SHELL ERROR] Exit code: {result.returncode}\n{error or output}"
        
        if output:
            return output
        elif error:
            return f"[SHELL OUTPUT]\n{error}"
        else:
            return "[SHELL SUCCESS] No output returned."
            
    except subprocess.TimeoutExpired:
        return "[ERROR] Command timed out after 60 seconds."
    except Exception as e:
        return f"[ERROR] Failed to execute command: {str(e)}"

if __name__ == "__main__":
    command = " ".join(sys.argv[1:])
    result = execute_shell(command)
    print(result)
