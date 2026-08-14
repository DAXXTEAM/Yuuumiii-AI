"""
Yuuumiii Telegram Bot - MEGA UPGRADE
Smart Intent Detection + Auto-Fix Monitor + Scheduler + Inline Buttons + Faster Responses + Memory Context
Commands: /pm2, /help, /status, /cancel, /schedule, /schedules, /unschedule + natural language tasks
"""
import asyncio
import json
import os
import subprocess
import sqlite3
import httpx
from pathlib import Path
from datetime import datetime

BOT_TOKEN = ""
OWNER_CHAT_ID = 8751571968
OPENCODE_KEY = "sk-mP4T4D48wiobgc3YTEf9wdDvuk1LwrujY076LgVxG0p3sR1kdgtAH1B0VTb1LRrk"
OPENCODE_URL = "https://opencode.ai/zen/v1"
CONFIG_PATH = '/root/Yuuumiii-AI/config.json'
API_BASE = "http://localhost:8080"
SCHEDULES_FILE = Path('/root/Yuuumiii-AI/schedules.json')
BRAIN_DB = '/root/Yuuumiii-AI/yuuumiii_brain.db'

SYSTEM = """Tu Yuuumiii hai - Arpit ki autonomous AI assistant Telegram pe.

Kaam karne ka tarika:
- Koi bhi action/task message aaye to autonomous agent use kar
- Seedha kaam kar, puchha mat kar
- Hindi/Hinglish mein jawab de
- Crisp aur useful reply de
- VPS access hai, GitHub access hai, sab hai

Owner: Arpit
Telegram ID: 8751571968
API_ID: 24509589
"""

# === SMART INTENT DETECTION ===
ACTION_WORDS = [
    'fix', 'deploy', 'install', 'create', 'update', 'restart', 'check',
    'setup', 'configure', 'run', 'start', 'stop', 'delete', 'add', 'remove',
    'krdo', 'karo', 'banao', 'lagao', 'chalao', 'hatao', 'dekho', 'test',
    'push', 'pull', 'clone', 'build', 'compile', 'monitor', 'debug',
    'repair', 'optimize', 'backup', 'migrate', 'scan', 'search'
]


def is_task(text):
    """Detect if message is a task (action) vs a question/chat"""
    text_lower = text.lower()
    return any(w in text_lower for w in ACTION_WORDS)


# Track active tasks being polled
active_polls = {}


def load_cfg():
    if Path(CONFIG_PATH).exists():
        try:
            return json.loads(Path(CONFIG_PATH).read_text())
        except:
            pass
    alt = '/root/daxx-assistant/config.json'
    if Path(alt).exists():
        try:
            return json.loads(Path(alt).read_text())
        except:
            pass
    return {}


# === FASTER RESPONSES - send_tg_get_id + edit_tg ===

async def send_tg(chat_id, text, token, parse_mode="HTML"):
    import re, html as _html
    safe = _html.escape(str(text))
    safe = re.sub(r"#{1,3} (.+)", r"<b>\\1</b>", safe)
    safe = re.sub(r"\*\*(.+?)\*\*", r"<b>\\1</b>", safe)
    safe = re.sub(r"\*([^*\n]+)\*", r"<i>\\1</i>", safe)
    safe = re.sub(r"`([^`]+)`", r"<code>\\1</code>", safe)
    payload = {"chat_id": chat_id, "text": safe[:4000]}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        async with httpx.AsyncClient() as c:
            await c.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload)
    except:
        pass


async def send_tg_get_id(chat_id, text, token, parse_mode="HTML"):
    """Send message and return message_id for later editing"""
    import re, html as _html
    safe = _html.escape(str(text))
    safe = re.sub(r"#{1,3} (.+)", r"<b>\\1</b>", safe)
    safe = re.sub(r"\*\*(.+?)\*\*", r"<b>\\1</b>", safe)
    safe = re.sub(r"\*([^*\n]+)\*", r"<i>\\1</i>", safe)
    safe = re.sub(r"`([^`]+)`", r"<code>\\1</code>", safe)
    payload = {"chat_id": chat_id, "text": safe[:4000]}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        async with httpx.AsyncClient() as c:
            r = await c.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload)
        return r.json().get('result', {}).get('message_id')
    except:
        return None


async def edit_tg(chat_id, message_id, text, token):
    """Edit an existing message by message_id"""
    if not message_id:
        return
    try:
        import html as _html
        safe = _html.escape(str(text))[:4000]
        async with httpx.AsyncClient() as c:
            await c.post(f"https://api.telegram.org/bot{token}/editMessageText",
                json={"chat_id": chat_id, "message_id": message_id, "text": safe, "parse_mode": "HTML"})
    except:
        pass


# === INLINE BUTTONS ===

async def send_tg_with_buttons(chat_id, text, token, task_id):
    """Send message with inline keyboard buttons"""
    import html as _html
    safe = _html.escape(str(text))[:4000]
    keyboard = {"inline_keyboard": [[
        {"text": "📊 Status", "callback_data": f"status_{task_id}"},
        {"text": "❌ Cancel", "callback_data": f"cancel_{task_id}"}
    ]]}
    try:
        async with httpx.AsyncClient() as c:
            await c.post(f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": safe, "reply_markup": keyboard, "parse_mode": "HTML"})
    except:
        pass


async def answer_callback(callback_id, text, token):
    """Answer a callback query (dismisses the loading indicator)"""
    try:
        async with httpx.AsyncClient() as c:
            await c.post(f"https://api.telegram.org/bot{token}/answerCallbackQuery",
                json={"callback_query_id": callback_id, "text": text[:200]})
    except:
        pass


# === MEMORY CONTEXT ===

def get_memory_context():
    """Load recent memories from brain DB for context"""
    try:
        if not Path(BRAIN_DB).exists():
            return ""
        conn = sqlite3.connect(BRAIN_DB)
        rows = conn.execute("SELECT content FROM memories ORDER BY created_at DESC LIMIT 6").fetchall()
        conn.close()
        return "\n".join([r[0] for r in rows if r[0]])
    except:
        return ""


# === AI CHAT ===

async def ask_ai(text, history=None):
    if history is None:
        history = []
    msgs = history[-6:] + [{"role": "user", "content": text}]

    # Inject memory context
    memory_context = get_memory_context()
    system_prompt = SYSTEM
    if memory_context:
        system_prompt = SYSTEM + f"\n\nRecent context:\n{memory_context}"

    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(f"{OPENCODE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {OPENCODE_KEY}"},
                json={"model": "claude-sonnet-4-5",
                      "messages": [{"role": "system", "content": system_prompt}] + msgs,
                      "max_tokens": 500})
        d = r.json()
        if "choices" in d:
            return d["choices"][0]["message"]["content"]
        return "Error: " + str(d)[:100]
    except Exception as e:
        return f"Error: {str(e)[:100]}"


# === AUTONOMOUS TASK API ===

async def create_autonomous_task(task_desc):
    """Call the autonomous task API endpoint"""
    try:
        cfg = load_cfg()
        password = cfg.get('dashboard_password', cfg.get('password', 'yuuumiii2025'))
        async with httpx.AsyncClient(timeout=10) as c:
            login_r = await c.post(f"{API_BASE}/api/login", json={"password": password})
            cookies = login_r.cookies
            r = await c.post(f"{API_BASE}/api/autonomous-task",
                json={"task": task_desc}, cookies=cookies)
            return r.json()
    except Exception as e:
        return {"error": str(e)}


async def get_task_status(task_id):
    """Poll task status"""
    try:
        cfg = load_cfg()
        password = cfg.get('dashboard_password', cfg.get('password', 'yuuumiii2025'))
        async with httpx.AsyncClient(timeout=10) as c:
            login_r = await c.post(f"{API_BASE}/api/login", json={"password": password})
            cookies = login_r.cookies
            r = await c.get(f"{API_BASE}/task/{task_id}", cookies=cookies)
            return r.json()
    except Exception as e:
        return {"error": str(e)}


async def poll_task_until_done(chat_id, task_id, msg_id, token):
    """Background coroutine: poll task every 10s, edit message with progress"""
    max_polls = 30
    poll_count = 0

    while poll_count < max_polls:
        await asyncio.sleep(10)
        poll_count += 1

        status = await get_task_status(task_id)
        if isinstance(status, dict) and status.get('error'):
            await edit_tg(chat_id, msg_id, f"Task #{task_id} poll error: {status['error']}", token)
            break

        task_status = status.get('status', 'unknown')

        if task_status in ('completed', 'done'):
            result = status.get('result', 'No result')
            steps = status.get('steps', '?')
            msg = f"Task #{task_id} DONE\n\nResult: {result}\nSteps: {steps}"
            await edit_tg(chat_id, msg_id, msg, token)
            break
        elif task_status == 'failed':
            result = status.get('result', 'Unknown error')
            msg = f"Task #{task_id} FAILED\n\nReason: {result}"
            await edit_tg(chat_id, msg_id, msg, token)
            break
        elif poll_count % 3 == 0:
            logs = status.get('logs', [])
            last_log = logs[-1] if logs else 'Working...'
            progress = status.get('progress', 0)
            await edit_tg(chat_id, msg_id, f"Task #{task_id} [{progress}%]: {last_log}", token)

    active_polls.pop(task_id, None)


# === AUTO-FIX MONITOR ===

async def auto_monitor(token, owner_id):
    """Auto monitor VPS services and alert + fix crashed ones"""
    while True:
        await asyncio.sleep(300)  # 5 min
        try:
            cfg = load_cfg()
            vps_pass = cfg.get('vps_password', '')
            if not vps_pass:
                continue

            result = subprocess.run(
                ['sshpass', '-p', vps_pass, 'ssh', '-o', 'StrictHostKeyChecking=no',
                 '-o', 'PubkeyAuthentication=no', 'root@216.9.227.103',
                 'pm2 jlist 2>/dev/null'],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode != 0:
                continue

            services = json.loads(result.stdout)
            crashed = [s['name'] for s in services if s.get('pm2_env', {}).get('status') == 'errored']

            if crashed:
                for svc in crashed:
                    subprocess.run(
                        ['sshpass', '-p', vps_pass, 'ssh', '-o', 'StrictHostKeyChecking=no',
                         '-o', 'PubkeyAuthentication=no', 'root@216.9.227.103',
                         f'pm2 restart {svc}'],
                        capture_output=True, timeout=10
                    )

                msg = f"AUTO-FIX: {', '.join(crashed)} crashed the - restarted automatically"
                await send_tg(owner_id, msg, token)
        except Exception:
            pass


# === SCHEDULER ===

def load_schedules():
    if SCHEDULES_FILE.exists():
        try:
            return json.loads(SCHEDULES_FILE.read_text())
        except:
            pass
    return []


def save_schedules(schedules):
    SCHEDULES_FILE.write_text(json.dumps(schedules, indent=2))


async def scheduler_loop(token, owner_id):
    """Run scheduled tasks - checks every minute"""
    last_run = ""
    while True:
        await asyncio.sleep(60)
        try:
            schedules = load_schedules()
            if not schedules:
                continue
            now = datetime.now().strftime('%H:%M')
            if now == last_run:
                continue
            last_run = now

            for s in schedules:
                if s.get('time') == now:
                    task = s.get('task', '')
                    if task:
                        msg_id = await send_tg_get_id(owner_id, f"Scheduled task running: {task}", token)
                        result = await create_autonomous_task(task)
                        if result.get('error'):
                            await edit_tg(owner_id, msg_id, f"Scheduled task failed: {result['error']}", token)
                        else:
                            task_id = result.get('task_id', '')
                            await edit_tg(owner_id, msg_id, f"Scheduled task #{task_id} started: {task}", token)
                            if task_id:
                                active_polls[task_id] = True
                                asyncio.create_task(poll_task_until_done(owner_id, task_id, msg_id, token))
        except Exception:
            pass


# === MAIN BOT LOOP ===

async def run_bot():
    cfg = load_cfg()
    token = cfg.get("telegram_bot_token", "")
    if not token:
        print("[Yuuumiii Bot] No telegram_bot_token in config.")
        return

    offset = 0
    histories = {}
    print("[Yuuumiii Bot] MEGA UPGRADE - Smart Intent + Auto-Fix + Scheduler + Inline Buttons!")

    # Start background coroutines
    asyncio.create_task(auto_monitor(token, OWNER_CHAT_ID))
    asyncio.create_task(scheduler_loop(token, OWNER_CHAT_ID))

    while True:
        try:
            async with httpx.AsyncClient(timeout=35) as c:
                r = await c.get(f"https://api.telegram.org/bot{token}/getUpdates",
                               params={"offset": offset, "timeout": 30, "allowed_updates": json.dumps(["message", "callback_query"])})
                updates = r.json().get("result", [])

            for upd in updates:
                offset = upd["update_id"] + 1

                # === HANDLE CALLBACK QUERIES (Inline Buttons) ===
                cb = upd.get("callback_query")
                if cb:
                    cb_id = cb.get("id", "")
                    cb_data = cb.get("data", "")
                    cb_chat = cb.get("message", {}).get("chat", {}).get("id")

                    if cb_chat != OWNER_CHAT_ID:
                        await answer_callback(cb_id, "Access denied", token)
                        continue

                    if cb_data.startswith("status_"):
                        task_id = cb_data.replace("status_", "")
                        status = await get_task_status(task_id)
                        s = status.get('status', '?')
                        p = status.get('progress', 0)
                        await answer_callback(cb_id, f"Status: {s} [{p}%]", token)

                    elif cb_data.startswith("cancel_"):
                        task_id = cb_data.replace("cancel_", "")
                        try:
                            cfg2 = load_cfg()
                            pw = cfg2.get('dashboard_password', cfg2.get('password', 'yuuumiii2025'))
                            async with httpx.AsyncClient(timeout=10) as c2:
                                lr = await c2.post(f"{API_BASE}/api/login", json={"password": pw})
                                r2 = await c2.post(f"{API_BASE}/task/{task_id}/cancel", cookies=lr.cookies)
                            await answer_callback(cb_id, "Task cancelled", token)
                        except:
                            await answer_callback(cb_id, "Cancel failed", token)
                    continue

                # === HANDLE MESSAGES ===
                msg = upd.get("message", {})
                chat_id = msg.get("chat", {}).get("id")
                text = msg.get("text", "")

                if not chat_id or not text:
                    continue

                if chat_id != OWNER_CHAT_ID:
                    await send_tg(chat_id, "Access denied.", token)
                    continue

                # === COMMANDS ===

                if text == "/start":
                    await send_tg(chat_id, "Namaste! Main Yuuumiii hoon - MEGA UPGRADE mode.\n\nAb /task likhne ki zarurat nahi - seedha bol kya karna hai!\n\nCommands:\n/pm2 - PM2 services\n/status - Task status\n/schedule HH:MM task - Schedule a daily task\n/schedules - List schedules\n/unschedule N - Remove schedule\n/help - Help", token)
                    continue

                if text == "/help":
                    help_text = """Yuuumiii MEGA - Commands:

Smart Mode (no /task needed):
  Just type what you want done!
  "Check PM2 services"
  "Fix crash in server.py"
  "Deploy latest code"

/pm2 - PM2 services status
/status [task_id] - Task status
/cancel <task_id> - Cancel task
/schedule HH:MM <task> - Daily scheduled task
/schedules - List all schedules
/unschedule <index> - Remove schedule
/help - This help

Normal questions = AI chat
Action messages = Autonomous agent"""
                    await send_tg(chat_id, help_text, token)
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

                if text.startswith("/status"):
                    parts = text.split(None, 1)
                    if len(parts) < 2:
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
                        r_val = status.get('result', '-')
                        logs = status.get('logs', [])
                        last_logs = "\n".join(logs[-3:]) if logs else "No logs"
                        msg_text = f"Task #{task_id}\nStatus: {s}\nProgress: {p}%\nResult: {r_val}\n\nLast logs:\n{last_logs}"
                        await send_tg(chat_id, msg_text, token)
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

                # === SCHEDULE COMMANDS ===

                if text.startswith("/schedule "):
                    # /schedule HH:MM task description
                    parts = text[10:].strip().split(None, 1)
                    if len(parts) < 2:
                        await send_tg(chat_id, "Usage: /schedule HH:MM <task description>\nExample: /schedule 02:00 Check VPS services", token)
                        continue
                    time_str = parts[0]
                    task_desc = parts[1]
                    # Validate time format
                    try:
                        datetime.strptime(time_str, '%H:%M')
                    except ValueError:
                        await send_tg(chat_id, "Invalid time format. Use HH:MM (24h)\nExample: /schedule 14:30 Restart services", token)
                        continue
                    schedules = load_schedules()
                    schedules.append({"time": time_str, "task": task_desc})
                    save_schedules(schedules)
                    await send_tg(chat_id, f"Schedule added!\nTime: {time_str} daily\nTask: {task_desc}\n\nTotal schedules: {len(schedules)}", token)
                    continue

                if text == "/schedules":
                    schedules = load_schedules()
                    if not schedules:
                        await send_tg(chat_id, "No schedules set.\nUse: /schedule HH:MM <task>", token)
                        continue
                    lines = []
                    for i, s in enumerate(schedules):
                        lines.append(f"[{i}] {s.get('time','')} - {s.get('task','')}")
                    await send_tg(chat_id, "Scheduled Tasks:\n" + "\n".join(lines) + "\n\nRemove: /unschedule <index>", token)
                    continue

                if text.startswith("/unschedule"):
                    parts = text.split(None, 1)
                    if len(parts) < 2:
                        await send_tg(chat_id, "Usage: /unschedule <index>\nUse /schedules to see indices.", token)
                        continue
                    try:
                        idx = int(parts[1].strip())
                        schedules = load_schedules()
                        if 0 <= idx < len(schedules):
                            removed = schedules.pop(idx)
                            save_schedules(schedules)
                            await send_tg(chat_id, f"Removed schedule [{idx}]: {removed.get('time','')} - {removed.get('task','')}", token)
                        else:
                            await send_tg(chat_id, f"Invalid index. Use /schedules to see valid indices.", token)
                    except ValueError:
                        await send_tg(chat_id, "Usage: /unschedule <number>", token)
                    continue

                # === SMART INTENT DETECTION ===
                # Legacy /task support (still works)
                if text.startswith("/task "):
                    task_desc = text[6:].strip()
                    if not task_desc:
                        await send_tg(chat_id, "Task description do.", token)
                        continue
                    # Route to autonomous
                    msg_id = await send_tg_get_id(chat_id, f"Working on it...\nTask: {task_desc}", token)
                    result = await create_autonomous_task(task_desc)
                    if result.get('error'):
                        await edit_tg(chat_id, msg_id, f"Task error: {result['error']}", token)
                        continue
                    task_id = result.get('task_id', '')
                    await edit_tg(chat_id, msg_id, f"Task #{task_id} started: {task_desc}", token)
                    await send_tg_with_buttons(chat_id, f"Task #{task_id} running - agent working...", token, task_id)
                    if task_id:
                        active_polls[task_id] = True
                        asyncio.create_task(poll_task_until_done(chat_id, task_id, msg_id, token))
                    continue

                # Smart detection: action message without /task prefix
                if is_task(text):
                    task_desc = text.strip()
                    msg_id = await send_tg_get_id(chat_id, f"Working on it...\nTask: {task_desc}", token)
                    result = await create_autonomous_task(task_desc)
                    if result.get('error'):
                        await edit_tg(chat_id, msg_id, f"Task error: {result['error']}", token)
                        continue
                    task_id = result.get('task_id', '')
                    await edit_tg(chat_id, msg_id, f"Task #{task_id} started: {task_desc}", token)
                    await send_tg_with_buttons(chat_id, f"Task #{task_id} running - agent working...", token, task_id)
                    if task_id:
                        active_polls[task_id] = True
                        asyncio.create_task(poll_task_until_done(chat_id, task_id, msg_id, token))
                    continue

                # === NORMAL AI CHAT (with memory context) ===
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
