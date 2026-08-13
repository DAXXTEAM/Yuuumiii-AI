import asyncio, json, httpx, psutil, datetime
from pathlib import Path
from core.brain import save_memory

CONFIG_PATH = '/root/daxx-assistant/config.json'
EVENTS_FILE = '/root/daxx-assistant/automation_events.json'

def load_events():
    if Path(EVENTS_FILE).exists():
        return json.loads(Path(EVENTS_FILE).read_text())
    return []

def save_events(events):
    Path(EVENTS_FILE).write_text(json.dumps(events, indent=2))

def default_events():
    return [
        {
            "id": "cpu_alert",
            "name": "CPU High Alert",
            "type": "system",
            "condition": "cpu > 85",
            "action": "notify",
            "message": "VPS CPU usage is {value}% - high load detected",
            "active": True,
            "last_triggered": None,
            "cooldown_minutes": 30
        },
        {
            "id": "ram_alert",
            "name": "RAM High Alert",
            "type": "system",
            "condition": "ram > 90",
            "action": "notify",
            "message": "VPS RAM usage is {value}% - memory critical",
            "active": True,
            "last_triggered": None,
            "cooldown_minutes": 30
        },
        {
            "id": "daily_report",
            "name": "Daily Morning Report",
            "type": "schedule",
            "condition": "time == 09:00",
            "action": "report",
            "active": True,
            "last_triggered": None,
            "cooldown_minutes": 1380
        }
    ]

async def send_telegram_notify(message, cfg):
    token = cfg.get('telegram_bot_token','')
    chat_id = 8751571968
    if not token:
        return
    try:
        async with httpx.AsyncClient() as c:
            await c.post(f"https://api.telegram.org/bot{token}/sendMessage",
                        json={"chat_id": chat_id, "text": f"[YUUUMIII ALERT]\n{message}"})
    except:
        pass

async def generate_daily_report():
    from core.brain import get_memory_stats, get_recent_memories
    stats = get_memory_stats()
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    recent = get_recent_memories(5)

    report = f"""Daily Report - {datetime.datetime.now().strftime('%Y-%m-%d')}

System Status:
  CPU: {cpu:.1f}%
  RAM: {ram:.1f}%
  Disk: {disk:.1f}%

Memory Stats:
  Total conversations: {stats['total_memories']}
  Saved facts: {stats['facts']}

Recent Activity:
"""
    for m in recent[-3:]:
        if m['role'] == 'user':
            report += f"  - {m['content'][:80]}...\n"

    return report

async def check_events():
    """Main automation loop - runs every 60 seconds"""
    if not Path(EVENTS_FILE).exists():
        save_events(default_events())

    while True:
        try:
            events = load_events()
            cfg = json.loads(Path(CONFIG_PATH).read_text()) if Path(CONFIG_PATH).exists() else {}
            now = datetime.datetime.now()

            cpu = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory().percent
            disk = psutil.disk_usage('/').percent

            for event in events:
                if not event.get('active', True):
                    continue

                # Check cooldown
                last = event.get('last_triggered')
                if last:
                    last_dt = datetime.datetime.fromisoformat(last)
                    cooldown = event.get('cooldown_minutes', 30)
                    if (now - last_dt).total_seconds() < cooldown * 60:
                        continue

                triggered = False
                value = None

                cond = event.get('condition', '')

                # System conditions
                if 'cpu >' in cond:
                    threshold = float(cond.split('>')[1].strip())
                    if cpu > threshold:
                        triggered = True
                        value = cpu

                elif 'ram >' in cond:
                    threshold = float(cond.split('>')[1].strip())
                    if ram > threshold:
                        triggered = True
                        value = ram

                elif 'disk >' in cond:
                    threshold = float(cond.split('>')[1].strip())
                    if disk > threshold:
                        triggered = True
                        value = disk

                # Schedule condition
                elif 'time ==' in cond:
                    target_time = cond.split('==')[1].strip()
                    current_time = now.strftime('%H:%M')
                    if current_time == target_time:
                        triggered = True

                if triggered:
                    event['last_triggered'] = now.isoformat()
                    action = event.get('action', 'notify')

                    if action == 'notify':
                        msg = event.get('message','Alert triggered').format(value=f"{value:.1f}" if value else "N/A")
                        await send_telegram_notify(msg, cfg)
                        save_memory('system', f'[AUTO] {msg}', importance=2)

                    elif action == 'report':
                        report = await generate_daily_report()
                        await send_telegram_notify(report, cfg)
                        save_memory('system', '[AUTO] Daily report sent', importance=1)

            save_events(events)

        except Exception as e:
            print(f"Automator error: {e}")

        await asyncio.sleep(60)

def start_automator():
    """Start automation engine in background"""
    import threading
    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(check_events())
    t = threading.Thread(target=run, daemon=True)
    t.start()
    print("Automation engine started")
