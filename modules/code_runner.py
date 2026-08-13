import subprocess, tempfile, os


def run(language: str, code: str) -> str:
    try:
        if language == "python":
            with tempfile.NamedTemporaryFile(suffix='.py', mode='w', delete=False) as f:
                f.write(code)
                fname = f.name
            r = subprocess.run(['python3', fname], capture_output=True, text=True, timeout=15)
            os.unlink(fname)
        elif language == "bash":
            r = subprocess.run(code, shell=True, capture_output=True, text=True, timeout=15)
        else:
            return f"Unsupported language: {language}"
        return (r.stdout + r.stderr).strip()[:2000] or "No output"
    except subprocess.TimeoutExpired:
        return "Timeout (15s)"
    except Exception as e:
        return f"Error: {e}"
