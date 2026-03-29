import subprocess
import sys
import platform

def execute_curl(args):
    if not args:
        return "[ERROR] No arguments provided. Usage: execute.py <curl_arguments>"

    cmd = ["curl"] + args

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=30,
            shell=False,
            encoding='utf-8',
            errors='ignore'
        )
        
        output = result.stdout.strip() if result.stdout else ""
        error = result.stderr.strip() if result.stderr else ""

        if result.returncode != 0:
            return f"[CURL ERROR] Exit code: {result.returncode}\n{error or output}"
        
        if output:
            return output
        elif error:
            return f"[CURL OUTPUT]\n{error}"
        else:
            return "[CURL SUCCESS] No output returned."
            
    except subprocess.TimeoutExpired:
        return "[ERROR] Curl command timed out after 30 seconds."
    except FileNotFoundError:
        return "[ERROR] 'curl' command not found. Please install curl or ensure it's in your PATH."
    except Exception as e:
        return f"[ERROR] Failed to execute curl: {str(e)}"

if __name__ == "__main__":
    args = sys.argv[1:]
    result = execute_curl(args)
    print(result)
