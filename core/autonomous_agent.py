"""
Yuuumiii Autonomous Agent - Multi-step task executor
Agentic loop: Plan -> Execute -> Verify -> Loop until done
Supports: VPS commands, file I/O, GitHub, Web Search, PM2
"""
import os
import json
import re
import time
import requests
import base64

OPENCODE_URL = "https://opencode.ai/zen/v1"
MODEL = "claude-sonnet-4-5"
VPS_HOST = "216.9.227.103"


def get_config():
    try:
        with open('/root/Yuuumiii-AI/config.json') as f:
            return json.load(f)
    except:
        return {}


def get_key():
    cfg = get_config()
    return cfg.get('opencode_api_key') or cfg.get('api_key')


def get_github_token():
    cfg = get_config()
    return cfg.get('github_token', '')


AGENT_SYSTEM = """You are Yuuumiii, an autonomous AI agent with full VPS and GitHub access.

You can execute tasks using these tools (write EXACTLY as shown):

== VPS TOOLS ==
[VPS_CMD: command here]     - Run any bash command on the VPS
[READ_FILE: /path/to/file]  - Read file contents from VPS
[WRITE_FILE: /path/to/file]
content here
[/WRITE_FILE]               - Write content to file on VPS

== PM2 TOOLS ==
[PM2_CMD: list]             - List all PM2 services
[PM2_CMD: restart <name>]   - Restart a PM2 service
[PM2_CMD: stop <name>]      - Stop a PM2 service
[PM2_CMD: logs <name>]      - Get recent logs of a PM2 service
[PM2_CMD: start <name>]     - Start a PM2 service

== GITHUB TOOLS ==
[GITHUB_LIST: owner/repo]              - List repo root files
[GITHUB_LIST: owner/repo/path/to/dir]  - List directory contents
[GITHUB_READ: owner/repo/path/to/file] - Read file from GitHub repo
[GITHUB_WRITE: owner/repo/path/to/file]
file content here
[/GITHUB_WRITE]                        - Commit/update file to GitHub repo

== SEARCH TOOLS ==
[WEB_SEARCH: search query here]  - Search the web for information

== CONTROL ==
[TASK_DONE: summary]        - Mark task as complete with summary
[TASK_FAILED: reason]       - Mark task as failed with reason

Rules:
- Break complex tasks into small steps
- Always verify after each action (check output, test the fix)
- For code fixes: read file -> understand -> fix -> write -> test -> verify
- Be autonomous - don't ask for confirmation, just do it
- Max 10 steps, then summarize what was done
- VPS user is root, all paths accessible
- Use Hindi/Hinglish in final summaries
- For GitHub edits: read current file first, then write the fixed version

Current VPS: 216.9.227.103 (Ubuntu 22.04)
Services managed via pm2. Projects under /root/
GitHub user: DAXXTEAM
"""


def run_vps_cmd(cmd, vps_password):
    """Execute command on VPS via SSH using paramiko"""
    import paramiko
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(VPS_HOST, username='root', password=vps_password, timeout=15)
        stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
        out = stdout.read().decode() + stderr.read().decode()
        client.close()
        return out.strip()[:2000] if out.strip() else "(no output)"
    except Exception as e:
        return f"SSH Error: {e}"


def read_file_vps(path, vps_password):
    return run_vps_cmd(f"cat {path} 2>&1 | head -200", vps_password)


def write_file_vps(path, content, vps_password):
    """Write file via SSH using paramiko SFTP"""
    import paramiko
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(VPS_HOST, username='root', password=vps_password, timeout=15)
        sftp = client.open_sftp()
        with sftp.file(path, 'w') as f:
            f.write(content)
        sftp.close()
        client.close()
        return "File written successfully"
    except Exception as e:
        return f"Write Error: {e}"


def pm2_command(action, vps_password):
    """Execute PM2 command on VPS"""
    parts = action.strip().split(None, 1)
    cmd_type = parts[0].lower() if parts else 'list'
    service = parts[1] if len(parts) > 1 else ''

    pm2_cmds = {
        'list': 'pm2 list',
        'restart': f'pm2 restart {service}' if service else 'pm2 restart all',
        'stop': f'pm2 stop {service}' if service else 'echo "Specify service name"',
        'start': f'pm2 start {service}' if service else 'echo "Specify service name"',
        'logs': f'pm2 logs {service} --lines 30 --nostream' if service else 'pm2 logs --lines 20 --nostream',
        'status': 'pm2 jlist',
    }

    cmd = pm2_cmds.get(cmd_type, f'pm2 {action}')
    return run_vps_cmd(cmd, vps_password)


def github_list(path_str):
    """List files in a GitHub repo directory"""
    token = get_github_token()
    if not token:
        return "Error: No GitHub token configured"

    parts = path_str.strip().split('/', 2)
    if len(parts) < 2:
        return "Error: Format should be owner/repo or owner/repo/path"

    owner = parts[0]
    repo = parts[1]
    path = parts[2] if len(parts) > 2 else ''

    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    try:
        r = requests.get(url, headers={
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }, timeout=15)
        if r.status_code == 404:
            return f"Error: Path not found - {owner}/{repo}/{path}"
        data = r.json()
        if isinstance(data, list):
            items = []
            for item in data:
                icon = "DIR " if item['type'] == 'dir' else "FILE"
                items.append(f"  {icon} {item['name']}")
            return f"Contents of {owner}/{repo}/{path or '/'}:\n" + "\n".join(items)
        return f"Error: Unexpected response: {str(data)[:200]}"
    except Exception as e:
        return f"GitHub Error: {e}"


def github_read(path_str):
    """Read a file from GitHub"""
    token = get_github_token()
    if not token:
        return "Error: No GitHub token configured"

    parts = path_str.strip().split('/', 2)
    if len(parts) < 3:
        return "Error: Format should be owner/repo/path/to/file"

    owner = parts[0]
    repo = parts[1]
    path = parts[2]

    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    try:
        r = requests.get(url, headers={
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }, timeout=15)
        if r.status_code == 404:
            return f"Error: File not found - {path}"
        data = r.json()
        if 'content' in data:
            content = base64.b64decode(data['content']).decode('utf-8', errors='replace')
            return content[:3000]
        return f"Error: No content in response"
    except Exception as e:
        return f"GitHub Read Error: {e}"


def github_write(path_str, content):
    """Write/commit a file to GitHub"""
    token = get_github_token()
    if not token:
        return "Error: No GitHub token configured"

    parts = path_str.strip().split('/', 2)
    if len(parts) < 3:
        return "Error: Format should be owner/repo/path/to/file"

    owner = parts[0]
    repo = parts[1]
    path = parts[2]

    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }

    # Check if file exists (get SHA for update)
    sha = None
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            sha = r.json().get('sha')
    except:
        pass

    # Create or update file
    payload = {
        'message': f'Yuuumiii Agent: Update {path}',
        'content': base64.b64encode(content.encode('utf-8')).decode('ascii'),
        'branch': 'main'
    }
    if sha:
        payload['sha'] = sha

    try:
        r = requests.put(url, headers=headers, json=payload, timeout=15)
        if r.status_code in (200, 201):
            return f"Successfully committed {path} to {owner}/{repo}"
        return f"GitHub Write Error {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return f"GitHub Write Error: {e}"


def web_search(query):
    """Search the web using DuckDuckGo HTML"""
    try:
        r = requests.get(
            'https://html.duckduckgo.com/html/',
            params={'q': query},
            headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'},
            timeout=10
        )
        # Extract result snippets from DDG HTML
        results = []
        from html.parser import HTMLParser

        class DDGParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.in_result = False
                self.in_snippet = False
                self.current_title = ''
                self.current_snippet = ''
                self.results = []

            def handle_starttag(self, tag, attrs):
                attrs_dict = dict(attrs)
                if tag == 'a' and 'result__a' in attrs_dict.get('class', ''):
                    self.in_result = True
                    self.current_title = ''
                if tag == 'a' and 'result__snippet' in attrs_dict.get('class', ''):
                    self.in_snippet = True
                    self.current_snippet = ''

            def handle_endtag(self, tag):
                if tag == 'a' and self.in_result:
                    self.in_result = False
                if tag == 'a' and self.in_snippet:
                    self.in_snippet = False
                    if self.current_title or self.current_snippet:
                        self.results.append(f"- {self.current_title}: {self.current_snippet}")

            def handle_data(self, data):
                if self.in_result:
                    self.current_title += data.strip()
                if self.in_snippet:
                    self.current_snippet += data.strip()

        parser = DDGParser()
        parser.feed(r.text)
        if parser.results:
            return f"Search results for '{query}':\n" + "\n".join(parser.results[:5])
        # Fallback: simple regex extraction
        snippets = re.findall(r'class="result__snippet">(.*?)</a>', r.text, re.DOTALL)
        if snippets:
            clean = [re.sub(r'<[^>]+>', '', s).strip() for s in snippets[:5]]
            return f"Search results for '{query}':\n" + "\n".join(f"- {s}" for s in clean if s)
        return f"No clear results found for: {query}"
    except Exception as e:
        return f"Search Error: {e}"


def call_llm(messages):
    key = get_key()
    if not key:
        return "Error: No API key configured"
    try:
        r = requests.post(
            f"{OPENCODE_URL}/chat/completions",
            headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
            json={'model': MODEL, 'messages': messages, 'max_tokens': 2500},
            timeout=60
        )
        data = r.json()
        if 'choices' in data:
            return data['choices'][0]['message']['content']
        return f"API Error: {data.get('error', str(data)[:200])}"
    except Exception as e:
        return f"LLM Error: {e}"


def execute_autonomous_task(task: str, vps_password: str, max_steps: int = 10, on_step=None):
    """
    Main agentic loop - executes task autonomously with tool use.

    Args:
        task: The task description
        vps_password: VPS root password
        max_steps: Maximum execution steps (default 10)
        on_step: Optional callback(step_num, description) for progress updates

    Returns:
        dict with keys: success, steps, result, total_steps
    """
    messages = [
        {"role": "system", "content": AGENT_SYSTEM},
        {"role": "user", "content": f"Task: {task}\n\nStart executing now. Be autonomous and complete the task."}
    ]

    steps = []
    step_num = 0

    while step_num < max_steps:
        step_num += 1

        if on_step:
            on_step(step_num, f"Thinking... (step {step_num}/{max_steps})")

        # Get AI response
        ai_response = call_llm(messages)
        steps.append({"step": step_num, "ai": ai_response[:500], "tool_results": []})

        # Check for LLM errors
        if ai_response.startswith("Error:") or ai_response.startswith("LLM Error:") or ai_response.startswith("API Error:"):
            return {"success": False, "steps": steps, "result": ai_response, "total_steps": step_num}

        # Execute tools found in response BEFORE checking done/failed
        tool_results = []

        # VPS_CMD
        for cmd_match in re.finditer(r'\[VPS_CMD:\s*(.*?)\]', ai_response, re.DOTALL):
            cmd = cmd_match.group(1).strip()
            if on_step:
                on_step(step_num, f"VPS: {cmd[:60]}")
            result = run_vps_cmd(cmd, vps_password)
            tool_results.append(f"[VPS_CMD: {cmd[:80]}]\nOutput:\n{result}")

        # READ_FILE
        for rf_match in re.finditer(r'\[READ_FILE:\s*(.*?)\]', ai_response):
            path = rf_match.group(1).strip()
            if on_step:
                on_step(step_num, f"Reading: {path}")
            result = read_file_vps(path, vps_password)
            tool_results.append(f"[READ_FILE: {path}]\nContent:\n{result}")

        # WRITE_FILE
        for wf_match in re.finditer(r'\[WRITE_FILE:\s*(.*?)\](.*?)\[/WRITE_FILE\]', ai_response, re.DOTALL):
            path = wf_match.group(1).strip()
            content = wf_match.group(2).strip()
            if on_step:
                on_step(step_num, f"Writing: {path}")
            result = write_file_vps(path, content, vps_password)
            tool_results.append(f"[WRITE_FILE: {path}]\nResult: {result}")

        # PM2_CMD
        for pm2_match in re.finditer(r'\[PM2_CMD:\s*(.*?)\]', ai_response):
            action = pm2_match.group(1).strip()
            if on_step:
                on_step(step_num, f"PM2: {action}")
            result = pm2_command(action, vps_password)
            tool_results.append(f"[PM2_CMD: {action}]\nOutput:\n{result}")

        # GITHUB_LIST
        for gl_match in re.finditer(r'\[GITHUB_LIST:\s*(.*?)\]', ai_response):
            path = gl_match.group(1).strip()
            if on_step:
                on_step(step_num, f"GitHub list: {path}")
            result = github_list(path)
            tool_results.append(f"[GITHUB_LIST: {path}]\n{result}")

        # GITHUB_READ
        for gr_match in re.finditer(r'\[GITHUB_READ:\s*(.*?)\]', ai_response):
            path = gr_match.group(1).strip()
            if on_step:
                on_step(step_num, f"GitHub read: {path}")
            result = github_read(path)
            tool_results.append(f"[GITHUB_READ: {path}]\n{result}")

        # GITHUB_WRITE
        for gw_match in re.finditer(r'\[GITHUB_WRITE:\s*(.*?)\](.*?)\[/GITHUB_WRITE\]', ai_response, re.DOTALL):
            path = gw_match.group(1).strip()
            content = gw_match.group(2).strip()
            if on_step:
                on_step(step_num, f"GitHub write: {path}")
            result = github_write(path, content)
            tool_results.append(f"[GITHUB_WRITE: {path}]\nResult: {result}")

        # WEB_SEARCH
        for ws_match in re.finditer(r'\[WEB_SEARCH:\s*(.*?)\]', ai_response):
            query = ws_match.group(1).strip()
            if on_step:
                on_step(step_num, f"Searching: {query[:40]}")
            result = web_search(query)
            tool_results.append(f"[WEB_SEARCH: {query}]\n{result}")

        steps[-1]["tool_results"] = tool_results

        # Check if task is done/failed (AFTER tool execution)
        if '[TASK_DONE:' in ai_response:
            match = re.search(r'\[TASK_DONE:\s*(.*?)\]', ai_response, re.DOTALL)
            summary = match.group(1).strip() if match else "Task completed"
            return {"success": True, "steps": steps, "result": summary, "total_steps": step_num}

        if '[TASK_FAILED:' in ai_response:
            match = re.search(r'\[TASK_FAILED:\s*(.*?)\]', ai_response, re.DOTALL)
            reason = match.group(1).strip() if match else "Task failed"
            return {"success": False, "steps": steps, "result": reason, "total_steps": step_num}

        # If no tools used, nudge the AI
        if not tool_results:
            tool_results.append("(No tools executed. Use a tool or mark [TASK_DONE: summary] / [TASK_FAILED: reason])")

        # Add tool results back to conversation
        tool_summary = "\n\n".join(tool_results)
        messages.append({"role": "assistant", "content": ai_response})
        messages.append({"role": "user", "content": f"Tool results:\n{tool_summary}\n\nContinue or mark [TASK_DONE: summary] if complete."})

    # Max steps reached
    return {
        "success": True,
        "steps": steps,
        "result": f"Max {step_num} steps reached. Task may need continuation.",
        "total_steps": step_num
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
    else:
        task = "Check pm2 list and report which services are running"

    vps_pass = os.environ.get('VPS_PASSWORD', '')
    if not vps_pass:
        print("Set VPS_PASSWORD env var")
        sys.exit(1)

    def progress(step, desc):
        print(f"  [{step}] {desc}")

    print(f"Task: {task}")
    print("=" * 50)
    result = execute_autonomous_task(task, vps_pass, max_steps=5, on_step=progress)
    print("=" * 50)
    print(f"Success: {result['success']}")
    print(f"Steps: {result['total_steps']}")
    print(f"Result: {result['result']}")
