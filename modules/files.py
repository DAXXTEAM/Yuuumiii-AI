import os


def read(path: str) -> str:
    try:
        return open(os.path.expanduser(path)).read()[:3000]
    except Exception as e:
        return f"Error: {e}"


def write(path: str, content: str) -> str:
    try:
        expanded = os.path.expanduser(path)
        dir_name = os.path.dirname(expanded)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(expanded, 'w') as f:
            f.write(content)
        return f"Written: {path}"
    except Exception as e:
        return f"Error: {e}"


def list_dir(path: str = ".") -> str:
    try:
        items = os.listdir(os.path.expanduser(path))
        return "\n".join(sorted(items))
    except Exception as e:
        return f"Error: {e}"
