import asyncio, json, os, httpx
from pathlib import Path

BOT_TOKEN = ""  # loaded from config
OWNER_CHAT_ID = 8751571968  # DAXX's Telegram ID
OPENCODE_KEY = "sk-mP4T4D48wiobgc3YTEf9wdDvuk1LwrujY076LgVxG0p3sR1kdgtAH1B0VTb1LRrk"
OPENCODE_URL = "https://opencode.ai/zen/v1"
CONFIG_PATH = '/root/daxx-assistant/config.json'

SYSTEM = "Aap Yuuumiii hain - DAXX ki AI assistant. Hindi/Hinglish mein baat karo. Koi emoji mat use karo. Short aur clear jawab do."

def load_cfg():
    if Path(CONFIG_PATH).exists():
        try:
            return json.loads(Path(CONFIG_PATH).read_text())
        except:
            pass
    return {}

async def send_tg(chat_id, text, token):
    async with httpx.AsyncClient() as c:
        await c.post(f"https://api.telegram.org/bot{token}/sendMessage",
                     json={"chat_id": chat_id, "text": text[:4000]})

async def ask_ai(text, history=None):
    if history is None:
        history = []
    msgs = history[-6:] + [{"role": "user", "content": text}]
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(f"{OPENCODE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {OPENCODE_KEY}"},
                json={"model": "claude-sonnet-4-5", "messages": [{"role": "system", "content": SYSTEM}] + msgs, "max_tokens": 400})
        d = r.json()
        if "choices" in d:
            return d["choices"][0]["message"]["content"]
        return "Error: " + str(d)[:100]
    except Exception as e:
        return f"Error: {str(e)[:100]}"

async def run_bot():
    cfg = load_cfg()
    token = cfg.get("telegram_bot_token", "")
    if not token:
        print("No telegram_bot_token in config. Add via /config page or config.json.")
        return

    offset = 0
    histories = {}
    print(f"Yuuumiii Telegram Bot started!")

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

                if text == "/start":
                    await send_tg(chat_id, "Namaste! Main Yuuumiii hoon. Kya madad karun?", token)
                    continue

                if text == "/status":
                    try:
                        async with httpx.AsyncClient() as c2:
                            r2 = await c2.get("http://localhost:8080/api/system")
                            sys_data = r2.json()
                        reply = f"System Status:\nCPU: {sys_data.get('cpu', 0):.1f}%\nRAM: {sys_data.get('ram', 0):.1f}%\nDisk: {sys_data.get('disk', 0):.1f}%"
                    except:
                        reply = "Status unavailable"
                    await send_tg(chat_id, reply, token)
                    continue

                if text == "/tasks":
                    try:
                        async with httpx.AsyncClient() as c2:
                            r2 = await c2.get("http://localhost:8080/task/status")
                            tasks = r2.json().get("tasks", [])
                        if tasks:
                            reply = "Active Tasks:\n" + "\n".join([f"- {t.get('title', '?')}: {t.get('status', '?')}" for t in tasks[-5:]])
                        else:
                            reply = "No tasks running."
                    except:
                        reply = "Tasks unavailable"
                    await send_tg(chat_id, reply, token)
                    continue

                # Normal chat
                h = histories.setdefault(chat_id, [])
                reply = await ask_ai(text, h)
                h.append({"role": "user", "content": text})
                h.append({"role": "assistant", "content": reply})
                if len(h) > 12:
                    h[:] = h[-12:]
                await send_tg(chat_id, reply, token)

        except Exception as e:
            print(f"Bot error: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(run_bot())
