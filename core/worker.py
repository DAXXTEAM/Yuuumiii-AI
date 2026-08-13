import asyncio
import paramiko
import httpx
import os

OPENCODE_KEY = "sk-mP4T4D48wiobgc3YTEf9wdDvuk1LwrujY076LgVxG0p3sR1kdgtAH1B0VTb1LRrk"
OPENCODE_URL = "https://opencode.ai/zen/v1"
VPS_HOST = "216.9.227.103"
VPS_USER = "root"

def run_ssh_command(cmd: str, password: str) -> str:
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(VPS_HOST, username=VPS_USER, password=password, timeout=15)
        stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
        out = stdout.read().decode() + stderr.read().decode()
        client.close()
        return out.strip()[:2000] if out.strip() else "(no output)"
    except Exception as e:
        return f"SSH Error: {str(e)}"


async def get_task_plan(task_description: str) -> list:
    """Ask Claude to plan the task into steps with VPS commands."""
    plan_prompt = f"""User wants this task done on a Linux VPS (Ubuntu, root access):
Task: {task_description}

Give me a JSON list of steps. Each step should have:
- "description": what this step does (short Hindi/Hinglish)  
- "command": the exact bash command to run on VPS

Return ONLY valid JSON array, no markdown, no explanation. Example:
[{{"description": "Disk space check", "command": "df -h"}}]

Max 5 steps. Only safe read/diagnostic commands unless task clearly needs writes."""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{OPENCODE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {OPENCODE_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "claude-sonnet-4-5",
                    "messages": [{"role": "user", "content": plan_prompt}],
                    "max_tokens": 500
                }
            )
            data = r.json()
            if "choices" not in data:
                return [{"description": "Direct execution", "command": task_description}]
            
            import json as _json
            content = data["choices"][0]["message"]["content"].strip()
            # Try to extract JSON from content
            if content.startswith("["):
                return _json.loads(content)
            # Try to find JSON in content
            import re
            match = re.search(r'\[.*\]', content, re.DOTALL)
            if match:
                return _json.loads(match.group())
            return [{"description": "Direct execution", "command": task_description}]
    except Exception as e:
        return [{"description": f"Fallback: {str(e)[:50]}", "command": task_description}]


async def execute_task(task_id: str, task_description: str, vps_password: str):
    """Execute a background task step by step."""
    from core.task_manager import task_manager

    task_manager.update_task(task_id, status="running", progress=5, log="Task started, planning steps...")
    await asyncio.sleep(0)

    # Get plan from Claude
    steps = await get_task_plan(task_description)
    total_steps = len(steps)
    task_manager.update_task(task_id, progress=10, log=f"Plan ready: {total_steps} steps")
    await asyncio.sleep(0)

    results = []
    for i, step in enumerate(steps):
        # Check if task was cancelled
        task = task_manager.get_task(task_id)
        if task and task["status"] == "failed":
            task_manager.update_task(task_id, log="Task cancelled, stopping execution")
            return

        desc = step.get("description", f"Step {i+1}")
        cmd = step.get("command", "echo 'no command'")
        
        progress = 10 + int((i + 1) / total_steps * 80)
        task_manager.update_task(task_id, progress=progress, log=f"[{i+1}/{total_steps}] {desc}")
        task_manager.update_task(task_id, log=f"CMD: {cmd}")
        await asyncio.sleep(0)

        # Execute command
        output = run_ssh_command(cmd, vps_password)
        results.append(f"Step {i+1} ({desc}):\n{output}")
        task_manager.update_task(task_id, log=f"Output: {output[:300]}")
        await asyncio.sleep(0.5)

    # Compile final result
    final_result = "\n\n".join(results)
    task_manager.update_task(task_id, status="done", progress=100, result=final_result, log="Task completed successfully")
