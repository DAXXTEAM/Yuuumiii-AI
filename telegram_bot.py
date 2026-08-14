"""
Yuuumiii Telegram Bot - with Autonomous Agent Integration
Commands: /task, /status, /pm2, /help, /cancel + normal chat
"""
import asyncio
import json
import os
import httpx
from pathlib import Path

BOT_TOKEN = ""
OWNER_CHAT_ID = 8751571968
OPENCODE_KEY = "sk-mP4T4D48wiobgc3YTEf9wdDvuk1LwrujY076LgVxG0p3sR1kdgtAH1B0VTb1LRrk"
OPENCODE_URL = "https://opencode.ai/zen/v1"
CONFIG_PATH = '/root/Yuuumiii-AI/config.json'
API_BASE = "http://localhost:8080"

SYSTEM = """Aap Yuuumiii hain - Arpit ki AI assistant. Hindi/Hinglish mein baat karo. Koi emoji mat use karo. Short aur clear jawab do.
Agar user koi complex task deta hai (fix code, deploy, check services, etc) to suggest karo ki /task command use kare."""

# Track active tasks being polled
active_polls = {}


def load_cfg():
    if Path(CONFIG_PATH).exists():
        try:
            return json.loads(Path(CONFIG_PATH).read_text())
        except:
            pass
    # Fallback
    alt = '/root/daxx-assistant/config.json'
    if Path(alt).exists():
        try:
            return json.loads(Path(alt).read_text())
        except:
            pass
    return {}


async def send_tg(chat_id, text, token, parse_mode=None):
    payload = {"chat_id": chat_id, "text": text[:4000]}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        async with httpx.AsyncClient() as c:
            await c.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload)
    except:
        pass


async def ask_ai(text, history=None):
    if history is None:
        history = []
    msgs = history[-6:] + [{"role": "user", "content": text}]
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(f"{OPENCODE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {OPENCODE_KEY}"},
                json={"model": "claude-sonnet-4-5",
                      "messages": [{"role": "system", "content": SYSTEM}] + msgs,
                      "max_tokens": 500})
        d = r.json()
        if "choices" in d:
            return d["choices"][0]["message"]["content"]
        return "Error: " + str(d)[:100]
    except Exception as e:
        return f"Error: {str(e)[:100]}"


async def create_autonomous_task(task_desc):
    """Call the autonomous task API endpoint"""
    try:
        # Get a session cookie first
        cfg = load_cfg()
        password = cfg.get('dashboard_password', cfg.get('password', 'yuuumiii2025'))

        async with httpx.AsyncClient(timeout=10) as c:
            # Login to get session
            login_r = await c.post(f"{API_BASE}/api/login",
                json={"password": password})
            cookies = login_r.cookies

            # Create task
            r = await c.post(f"{API_BASE}/api/autonomous-task",
                json={"task": task_desc},
                cookies=cookies)
            return r.json()
    except Exception as e:
        return {"error": str(e)}


async def get_task_status(task_id):
    """Poll task status"""
    try:
        cfg = load_cfg()
        password = cfg.get('dashboard_password', cfg.get('password', 'yuuumiii2025'))

        async with httpx.AsyncClient(timeout=10) as c:
            login_r = await c.post(f"{API_BASE}/api/login",
                json={"password": password})
            cookies = login_r.cookies

            r = await c.get(f"{API_BASE}/task/{task_id}", cookies=cookies)
            return r.json()
    except Exception as e:
        return {"error": str(e)}


async def poll_task_until_done(chat_id, task_id, token):
    """Background coroutine: poll task every 10s, send result when done"""
    max_polls = 30  # max 5 minutes
    poll_count = 0

    while poll_count < max_polls:
        await asyncio.sleep(10)
        poll_count += 1

        status = await get_task_status(task_id)
        if isinstance(status, dict) and status.get('error'):
            await send_tg(chat_id, f"Task #{task_id} poll error: {status['error']}", token)
            break

        task_status = status.get('status', 'unknown')

        if task_status in ('completed', 'done'):
            result = status.get('result', 'No result')
            steps = status.get('steps', '?')
            msg = f"Task #{task_id} DONE\n\nResult: {result}\nSteps: {steps}"
            await send_tg(chat_id, msg, token)
            break
        elif task_status == 'failed':
            result = status.get('result', 'Unknown error')
            msg = f"Task #{task_id} FAILED\n\nReason: {result}"
            await send_tg(chat_id, msg, token)
            break
        elif poll_count % 3 == 0:
            # Every 30s send progress update
            logs = status.get('logs', [])
            last_log = logs[-1] if logs else 'Working...'
            progress = status.get('progress', 0)
            await send_tg(chat_id, f"Task #{task_id} [{progress}%]: {last_log}", token)

    # Remove from active
    active_polls.pop(task_id, None)


async def run_bot():
    cfg = load_cfg()
    token = cfg.get("telegram_bot_token", "")
    if not token:
        print("[Yuuumiii Bot] No telegram_bot_token in config.")
        return

    offset = 0
    histories = {}
    print("[Yuuumiii Bot] Started with autonomous agent support!")

    while True:
        try:
            async with httpx.AsyncClient(timeout=35) as c:
                r = await c.get(f"https://api.telegram.org/bot{token}/getUpdates",
                               params={"offset": offset, "timeout": 30})
                updates = r.json().get("result", [])

            for upd in updates:
                offset = upd["update_id"] + 1
                msg = upd.get("message", {})
                chat_id = msg.get("chat", {}).get("id")
                text = msg.get("text", "")

                if not chat_id or not text:
                    continue

                # Only respond to owner
                if chat_id != OWNER_CHAT_ID:
                    await send_tg(chat_id, "Access denied.", token)
                    continue

                # === COMMANDS ===

                if text == "/start":
                    await send_tg(chat_id, "Namaste! Main Yuuumiii hoon - autonomous agent mode ready.\n\nCommands:\n/task <description> - Autonomous task execute karo\n/status <task_id> - Task ka status check karo\n/pm2 - PM2 services dikhao\n/cancel <task_id> - Task cancel karo\n/help - Help dikhao", token)
                    continue

                if text == "/help":
                    help_text = """Yuuumiii Commands:

/task <description>
  Autonomous agent task - ye VPS pe commands chalayega, files read/write karega, GitHub access karega, sab khud se.
  Example: /task Fix crash in server.py and restart

/status <task_id>
  Task ka status aur progress check karo

/pm2
  All PM2 services ka status

/cancel <task_id>
  Running task cancel karo

Normal message = simple AI chat"""
                    await send_tg(chat_id, help_text, token)
                    continue

                if text.startswith("/task "):
                    task_desc = text[6:].strip()
                    if not task_desc:
                        await send_tg(chat_id, "Task description do. Example: /task Check all PM2 services", token)
                        continue

                    await send_tg(chat_id, f"Agent mode activated!\nTask: {task_desc}\nStarting autonomous execution...", token)

                    result = await create_autonomous_task(task_desc)
                    if result.get('error'):
                        await send_tg(chat_id, f"Task create error: {result['error']}", token)
                        continue

                    task_id = result.get('task_id', '')
                    await send_tg(chat_id, f"Task created: #{task_id}\nAgent working... updates har 30s aayenge.", token)

                    # Start background polling
                    if task_id:
                        active_polls[task_id] = True
                        asyncio.create_task(poll_task_until_done(chat_id, task_id, token))
                    continue

                if text.startswith("/status"):
                    parts = text.split(None, 1)
                    if len(parts) < 2:
                        # Show all recent tasks
                        try:
                            cfg2 = load_cfg()
                            pw = cfg2.get('dashboard_password', cfg2.get('password', 'yuuumiii2025'))
                            async with httpx.AsyncClient(timeout=10) as c2:
                                lr = await c2.post(f"{API_BASE}/api/login", json={"password": pw})
                                r2 = await c2.get(f"{API_BASE}/task/status", cookies=lr.cookies)
                                tasks = r2.json()
                            if isinstance(tasks, list) and tasks:
                                lines = []
                                for t in tasks[:5]:
                                    lines.append(f"#{t.get('id','?')} [{t.get('status','?')}] {t.get('title','')[:40]}")
                                await send_tg(chat_id, "Recent Tasks:\n" + "\n".join(lines), token)
                            else:
                                await send_tg(chat_id, "No tasks found.", token)
                        except Exception as e:
                            await send_tg(chat_id, f"Error: {e}", token)
                        continue

                    task_id = parts[1].strip().replace('#', '')
                    status = await get_task_status(task_id)
                    if status.get('error'):
                        await send_tg(chat_id, f"Error: {status['error']}", token)
                    else:
                        s = status.get('status', '?')
                        p = status.get('progress', 0)
                        r = status.get('result', '-')
                        logs = status.get('logs', [])
                        last_logs = "\n".join(logs[-3:]) if logs else "No logs"
                        msg = f"Task #{task_id}\nStatus: {s}\nProgress: {p}%\nResult: {r}\n\nLast logs:\n{last_logs}"
                        await send_tg(chat_id, msg, token)
                    continue

                if text == "/pm2":
                    try:
                        cfg2 = load_cfg()
                        pw = cfg2.get('dashboard_password', cfg2.get('password', 'yuuumiii2025'))
                        async with httpx.AsyncClient(timeout=10) as c2:
                            lr = await c2.post(f"{API_BASE}/api/login", json={"password": pw})
                            r2 = await c2.post(f"{API_BASE}/api/terminal",
                                json={"cmd": "pm2 list"}, cookies=lr.cookies)
                            output = r2.json().get("output", "No output")
                        await send_tg(chat_id, f"PM2 Services:\n{output}", token)
                    except Exception as e:
                        await send_tg(chat_id, f"PM2 Error: {e}", token)
                    continue

                if text.startswith("/cancel"):
                    parts = text.split(None, 1)
                    if len(parts) < 2:
                        await send_tg(chat_id, "Usage: /cancel <task_id>", token)
                        continue
                    task_id = parts[1].strip().replace('#', '')
                    try:
                        cfg2 = load_cfg()
                        pw = cfg2.get('dashboard_password', cfg2.get('password', 'yuuumiii2025'))
                        async with httpx.AsyncClient(timeout=10) as c2:
                            lr = await c2.post(f"{API_BASE}/api/login", json={"password": pw})
                            r2 = await c2.post(f"{API_BASE}/task/{task_id}/cancel", cookies=lr.cookies)
                            d = r2.json()
                        if d.get('ok'):
                            await send_tg(chat_id, f"Task #{task_id} cancelled.", token)
                        else:
                            await send_tg(chat_id, f"Cannot cancel: {d.get('message','')}", token)
                    except Exception as e:
                        await send_tg(chat_id, f"Cancel error: {e}", token)
                    continue

                # === NORMAL CHAT ===
                h = histories.setdefault(chat_id, [])
                reply = await ask_ai(text, h)
                h.append({"role": "user", "content": text})
                h.append({"role": "assistant", "content": reply})
                if len(h) > 12:
                    h[:] = h[-12:]
                await send_tg(chat_id, reply, token)

        except Exception as e:
            print(f"[Yuuumiii Bot] Error: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(run_bot())
