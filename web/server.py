import sys, os, json, re as _re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, BackgroundTasks, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
import asyncio
import secrets
import hashlib

import psutil
import uuid
from fastapi import UploadFile, File

import subprocess, tempfile, uuid as _uuid
import datetime as _dt
from core.brain import save_memory as brain_save_memory, get_recent_memories, search_memories, get_memory_stats, save_fact, get_all_facts, init_db
from core.automator import start_automator, load_events, save_events

UPLOAD_DIR = '/root/daxx-assistant/uploads'
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="Yuuumiii AI Assistant")
app.mount("/static", StaticFiles(directory="web/static"), name="static")


import datetime

HISTORY_FILE = '/root/daxx-assistant/chat_history.json'
MEMORY_FILE  = '/root/daxx-assistant/yuuumiii_memory.md'

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE) as f:
                return json.load(f)
        except: pass
    return []

def save_history(history):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def append_memory(user_msg, ai_reply, model):
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    entry = f"""
## [{ts}]
**User:** {user_msg[:300]}
**Yuuumiii ({model}):** {ai_reply[:500]}
---
"""
    with open(MEMORY_FILE, 'a', encoding='utf-8') as f:
        f.write(entry)

# Load history on startup
persistent_history = load_history()

conversation_history = persistent_history
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")

OPENCODE_KEY = "OPENCODE_KEY_HERE"
OPENCODE_URL = "https://opencode.ai/zen/v1"
VPS_HOST = "216.9.227.103"
VPS_USER = "root"
# Dynamic model selection
YUUUMIII_MODEL = "claude-sonnet-4-5"

# Load persisted model from config
_startup_cfg = {}
if os.path.exists(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")):
    try:
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")) as _f:
            _startup_cfg = json.load(_f)
        if _startup_cfg.get("selected_model"):
            YUUUMIII_MODEL = _startup_cfg["selected_model"]
    except: pass


YUUUMIII_SYSTEM = """Aap Yuuumiii hain - DAXX ki powerful AI assistant. Claude Sonnet 4.5 use karti hain.

Aap VPS se connected hain (216.9.227.103). Jab user kuch karne ko bole:
- Agar VPS command chahiye to [VPS_CMD: command_here] format mein likho
- Agar file banana ho to [VPS_CMD: cat > /path/file << 'EOF'\ncontent\nEOF] 
- Normal jawab bhi do result ke saath

Jab user koi lamba kaam karne ko bole (VPS pe kuch banao, files process karo, research karo etc.) to [BACKGROUND_TASK: task description here] format use karo. Normal sawaalon ka jawab normal do.

Rules:
- Naam hamesha Yuuumiii
- Hindi/Hinglish mein baat karo
- Koi emoji mat use karo
- Plain text
- Direct kaam karo, guide mat karo
- [VPS_CMD: ...] use karo jab VPS pe kuch karna ho
- [BACKGROUND_TASK: ...] use karo jab lamba kaam background mein karna ho"""

# Background task keywords
TASK_KEYWORDS = ["background mein", "task do", "baad mein karo", "schedule karo", "run karo", "kaam karo"]

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}

def clean_text(text):
    text = _re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = _re.sub(r'\*(.+?)\*', r'\1', text)
    text = _re.sub(r'#{1,6}\s+', '', text)
    text = _re.sub(r'```[\s\S]*?```', '', text)
    text = _re.sub(r'`([^`]+)`', r'\1', text)
    text = _re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    text = _re.sub(r'[\U00010000-\U0010ffff]', '', text)
    text = _re.sub(r'[\u2600-\u27BF]', '', text)
    return text.strip()

def run_vps_cmd(cmd: str, password: str) -> str:
    import paramiko
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(VPS_HOST, username=VPS_USER, password=password, timeout=10)
        stdin, stdout, stderr = client.exec_command(cmd, timeout=20)
        out = stdout.read().decode() + stderr.read().decode()
        client.close()
        return out.strip()[:500] if out.strip() else '(no output)'
    except Exception as e:
        return f'Error: {str(e)}'

def extract_vps_commands(text: str):
    return _re.findall(r'\[VPS_CMD:\s*(.*?)\]', text, _re.DOTALL)

def detect_background_task(message: str) -> bool:
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in TASK_KEYWORDS)

def extract_background_tasks(text: str):
    return _re.findall(r'\[BACKGROUND_TASK:\s*(.*?)\]', text, _re.DOTALL)

class ChatRequest(BaseModel):
    message: str

class TaskRequest(BaseModel):
    task: str

# --- AUTH SYSTEM ---
SESSION_FILE = '/root/daxx-assistant/sessions.json'

def load_sessions():
    from pathlib import Path
    if Path(SESSION_FILE).exists():
        try:
            import json as _json
            return set(_json.loads(Path(SESSION_FILE).read_text()))
        except: pass
    return set()

def save_sessions(tokens):
    import json as _json
    with open(SESSION_FILE,'w') as f:
        _json.dump(list(tokens), f)

SESSION_TOKENS = load_sessions()
DEFAULT_PASSWORD = "yuuumiii2025"

def check_auth(request: Request) -> bool:
    cfg = load_config()
    # If auth is disabled, allow all
    if not cfg.get('auth_enabled', True):
        return True
    token = request.cookies.get('yuuumiii_session')
    return token in SESSION_TOKENS

# --- Learning System Import ---
sys.path.insert(0, '/root/daxx-assistant')
try:
    from core.learning import learn_from_conversation, get_learning_context
except:
    def learn_from_conversation(u, a): pass
    def get_learning_context(): return ""

# --- Task System Imports ---
from core.task_manager import task_manager
from core.worker import execute_task

# --- Pages ---
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if not check_auth(request):
        return RedirectResponse('/login')
    from pathlib import Path
    html = Path(os.path.dirname(os.path.abspath(__file__))) / "templates" / "index.html"
    return HTMLResponse(html.read_text())

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not check_auth(request):
        return RedirectResponse('/login')
    from pathlib import Path
    html = Path(os.path.dirname(os.path.abspath(__file__))) / "templates" / "index.html"
    return HTMLResponse(html.read_text())

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    from pathlib import Path
    html = Path(os.path.dirname(os.path.abspath(__file__))) / "templates" / "login.html"
    return HTMLResponse(html.read_text())

@app.post("/api/login")
async def do_login(data: dict, response: Response):
    cfg = load_config()
    stored_pw = cfg.get('dashboard_password', DEFAULT_PASSWORD)
    if data.get('password') == stored_pw:
        token = secrets.token_hex(32)
        SESSION_TOKENS.add(token)
        save_sessions(SESSION_TOKENS)
        response.set_cookie('yuuumiii_session', token, httponly=True, max_age=86400*30, samesite='lax')
        return {'ok': True}
    return {'ok': False}

@app.post("/api/logout")
async def do_logout(request: Request, response: Response):
    token = request.cookies.get('yuuumiii_session')
    SESSION_TOKENS.discard(token)
    save_sessions(SESSION_TOKENS)
    response.delete_cookie('yuuumiii_session')
    return {'ok': True}

@app.get("/voice", response_class=HTMLResponse)
async def voice_page(request: Request):
    if not check_auth(request):
        return RedirectResponse('/login')
    from pathlib import Path
    html = Path(os.path.dirname(os.path.abspath(__file__))) / "templates" / "voice.html"
    return HTMLResponse(html.read_text())

@app.get("/tasks", response_class=HTMLResponse)
async def tasks_page(request: Request):
    if not check_auth(request):
        return RedirectResponse('/login')
    from pathlib import Path
    html = Path(os.path.dirname(os.path.abspath(__file__))) / "templates" / "tasks.html"
    return HTMLResponse(html.read_text())

# --- Task API Endpoints ---
@app.post("/task/create")
async def create_task(req: TaskRequest, request: Request, background_tasks: BackgroundTasks):
    if not check_auth(request):
        return {"error": "Unauthorized"}
    vps_pass = os.environ.get('VPS_PASSWORD', 'Wu2Vcvxv')
    task_id = task_manager.add_task(req.task)
    background_tasks.add_task(run_background_task, task_id, req.task, vps_pass)
    return {"task_id": task_id, "message": f"Task created: {task_id}"}

@app.get("/task/status")
async def task_status(request: Request):
    if not check_auth(request):
        return {"error": "Unauthorized"}
    return task_manager.get_all_tasks()

@app.get("/task/{task_id}")
async def task_detail(task_id: str, request: Request):
    if not check_auth(request):
        return {"error": "Unauthorized"}
    task = task_manager.get_task(task_id)
    if not task:
        return {"error": "Task not found"}
    return task

@app.post("/task/{task_id}/cancel")
async def cancel_task(task_id: str, request: Request):
    if not check_auth(request):
        return {"error": "Unauthorized"}
    success = task_manager.cancel_task(task_id)
    return {"ok": success, "message": "Cancelled" if success else "Cannot cancel"}

async def run_background_task(task_id: str, description: str, vps_password: str):
    try:
        await execute_task(task_id, description, vps_password)
    except Exception as e:
        task_manager.update_task(task_id, status="failed", log=f"Fatal error: {str(e)}")

# --- Chat ---
@app.post("/chat")
async def chat(req: ChatRequest, request: Request, background_tasks: BackgroundTasks):
    import httpx

    if not check_auth(request):
        return {"error": "Unauthorized"}

    cfg = load_config()
    vps_pass = os.environ.get('VPS_PASSWORD', 'Wu2Vcvxv')

    # Check if user explicitly wants a background task
    if detect_background_task(req.message):
        task_desc = req.message
        for kw in TASK_KEYWORDS:
            task_desc = task_desc.lower().replace(kw, "").strip()
        if not task_desc:
            task_desc = req.message
        
        task_id = task_manager.add_task(task_desc)
        background_tasks.add_task(run_background_task, task_id, task_desc, vps_pass)
        
        response_text = f"Background task created!\nTask ID: {task_id}\nDescription: {task_desc}\n\nStatus check karo: /tasks page pe ya /task/{task_id}"
        conversation_history.append({'role': 'user', 'content': req.message, 'time': datetime.datetime.now().strftime('%H:%M')})
        conversation_history.append({'role': 'assistant', 'content': response_text})
        return {'response': response_text, 'tools': ['background_task'], 'model': 'Task System', 'task_id': task_id}

    # --- FEATURE 6: Web Scraper - URL detection ---
    enhanced_msg = req.message
    urls = _re.findall(r'https?://[^\s]+', req.message)
    if urls:
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.get(urls[0], headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
                from html.parser import HTMLParser
                class TextExtract(HTMLParser):
                    def __init__(self):
                        super().__init__()
                        self.text = []
                    def handle_data(self, d):
                        self.text.append(d)
                p = TextExtract()
                p.feed(r.text)
                page_text = ' '.join(p.text)[:3000]
                enhanced_msg = req.message + f"\n\n[Webpage content from {urls[0]}]:\n{page_text}"
        except:
            enhanced_msg = req.message


    # --- FEATURE: Image Generation in chat ---
    img_triggers = ['image banao', 'imagine', 'generate image', 'photo banao', 'picture banao']
    msg_lower = req.message.lower().strip()
    if any(msg_lower.startswith(t) for t in img_triggers):
        import httpx as _httpx
        img_prompt = req.message
        for t in img_triggers:
            if msg_lower.startswith(t):
                img_prompt = req.message[len(t):].strip()
                break
        if img_prompt:
            try:
                async with _httpx.AsyncClient(timeout=30) as _c:
                    _r = await _c.post(f"{OPENCODE_URL}/images/generations",
                        headers={'Authorization': f'Bearer {OPENCODE_KEY}'},
                        json={'model': 'dall-e-3', 'prompt': img_prompt, 'n': 1, 'size': '512x512'})
                    _d = _r.json()
                    if 'data' in _d and len(_d['data']) > 0:
                        img_url = _d['data'][0].get('url', '')
                        img_response = f"Image generated: {img_url}"
                        conversation_history.append({'role': 'user', 'content': req.message, 'time': datetime.datetime.now().strftime('%H:%M')})
                        conversation_history.append({'role': 'assistant', 'content': img_response})
                        save_history(conversation_history)
                        return {'response': img_response, 'tools': ['image_gen'], 'model': 'DALL-E 3', 'image_url': img_url}
            except:
                pass

    # --- FEATURE: GitHub repos in chat ---
    if any(w in msg_lower for w in ['repos dikhao', 'github repos', 'my repos', 'mere repos']):
        cfg = load_config()
        if cfg.get('github_token'):
            import httpx as _httpx
            try:
                async with _httpx.AsyncClient(timeout=15) as _c:
                    _r = await _c.get(f"https://api.github.com/users/{cfg.get('github_username', '')}/repos?sort=updated&per_page=5",
                        headers={'Authorization': f'token {cfg["github_token"]}', 'Accept': 'application/vnd.github.v3+json'})
                    repos = _r.json()
                    if isinstance(repos, list):
                        repo_list = '\n'.join([f"- {repo.get('name','')}: {repo.get('description','') or 'No desc'}" for repo in repos[:5] if isinstance(repo, dict)])
                        enhanced_msg = req.message + f"\n\n[GitHub Repos]:\n{repo_list}"
            except:
                pass

    # --- FEATURE: Email send in chat ---
    email_match = _re.search(r'(?:email|mail)\s+(?:bhejo|send|karo).*?(?:to\s+|ko\s+)?([\w.]+@[\w.]+)', req.message, _re.I)
    if email_match:
        cfg = load_config()
        resend_key = cfg.get('resend_api_key', '')
        if resend_key:
            import httpx as _httpx
            to_email = email_match.group(1)
            subject_match = _re.search(r'subject[:\s]+(.+?)(?:\n|body|content|$)', req.message, _re.I)
            subject = subject_match.group(1).strip() if subject_match else 'Message from Yuuumiii'
            body_text = req.message
            try:
                async with _httpx.AsyncClient(timeout=15) as _c:
                    _r = await _c.post('https://api.resend.com/emails',
                        headers={'Authorization': f'Bearer {resend_key}', 'Content-Type': 'application/json'},
                        json={'from': cfg.get('business_email', 'yuuumiii@resend.dev'),
                              'to': [to_email], 'subject': subject, 'text': body_text})
                    email_result = _r.json()
                    enhanced_msg = req.message + f"\n\n[Email sent to {to_email}: {json.dumps(email_result)}]"
            except Exception as _e:
                enhanced_msg = req.message + f"\n\n[Email send failed: {str(_e)}]"

    # --- FEATURE: Invoice in chat ---
    if 'invoice banao' in msg_lower or 'invoice generate' in msg_lower:
        # Try to extract client and amount
        amount_match = _re.search(r'(\d+)', req.message)
        amount = int(amount_match.group(1)) if amount_match else 0
        client_match = _re.search(r'(?:client|for|ke liye)\s+([\w\s]+?)(?:\s+amount|\s+ka|\s+\d|$)', req.message, _re.I)
        client_name = client_match.group(1).strip() if client_match else 'Client'
        enhanced_msg = req.message + f"\n\n[Invoice request: Client={client_name}, Amount=Rs.{amount}]"


    # --- FEATURE 5: Learning context ---
    learning_ctx = get_learning_context()
    enhanced_system = YUUUMIII_SYSTEM
    if learning_ctx:
        enhanced_system = YUUUMIII_SYSTEM + "\n\nUser context: " + learning_ctx

    # --- LEVEL 4: Inject brain memory context ---
    try:
        recent_memories = get_recent_memories(limit=8)
        memory_ctx = '\n'.join([f"{m['role']}: {m['content'][:100]}" for m in recent_memories])
        if memory_ctx:
            enhanced_system += f"\n\n[MEMORY - Recent conversations]:\n{memory_ctx}"
    except:
        pass

    msgs = []
    for m in conversation_history[-10:]:
        if isinstance(m, dict) and m.get('role') in ('user', 'assistant') and isinstance(m.get('content'), str):
            msgs.append({'role': m['role'], 'content': m['content']})
    msgs.append({'role': 'user', 'content': enhanced_msg})

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{OPENCODE_URL}/chat/completions",
                headers={'Authorization': f'Bearer {OPENCODE_KEY}', 'Content-Type': 'application/json'},
                json={'model': YUUUMIII_MODEL, 'messages': [{'role': 'system', 'content': enhanced_system}] + msgs, 'max_tokens': 600}
            )
            data = r.json()

        if 'choices' not in data:
            return {'response': 'API error: ' + str(data.get('error', ''))[:100], 'tools': []}

        ai_reply = data['choices'][0]['message']['content'] or ''

        # Extract and run VPS commands
        tools_used = []
        vps_results = []
        if vps_pass:
            cmds = extract_vps_commands(ai_reply)
            for cmd in cmds:
                result = run_vps_cmd(cmd.strip(), vps_pass)
                vps_results.append(f"Result: {result}")
                tools_used.append('vps_exec')

        # Check if AI wants to create a background task
        bg_tasks = extract_background_tasks(ai_reply)
        for bt in bg_tasks:
            task_id = task_manager.add_task(bt.strip())
            background_tasks.add_task(run_background_task, task_id, bt.strip(), vps_pass)
            tools_used.append('background_task')
            vps_results.append(f"Background task created: {task_id}")

        # Remove [VPS_CMD:...] and [BACKGROUND_TASK:...] tags from reply
        clean_reply = _re.sub(r'\[VPS_CMD:.*?\]', '', ai_reply, flags=_re.DOTALL).strip()
        clean_reply = _re.sub(r'\[BACKGROUND_TASK:.*?\]', '', clean_reply, flags=_re.DOTALL).strip()
        clean_reply = clean_text(clean_reply)

        # Append VPS results to reply
        if vps_results:
            clean_reply = clean_reply + '\n\n' + '\n'.join(vps_results)

        conversation_history.append({'role': 'user', 'content': req.message, 'time': datetime.datetime.now().strftime('%H:%M')})
        conversation_history.append({'role': 'assistant', 'content': clean_reply})
        if len(conversation_history) > 20:
            conversation_history[:] = conversation_history[-20:]
        
        # Save history
        save_history(conversation_history)

        # Save to AI brain long-term memory
        brain_save_memory('user', req.message)
        brain_save_memory('assistant', clean_reply, importance=2)

        # Learn from conversation
        learn_from_conversation(req.message, clean_reply)

        return {'response': clean_reply, 'tools': tools_used, 'model': YUUUMIII_MODEL}

    except Exception as e:
        return {'response': 'Error: ' + str(e)[:100], 'tools': []}

# --- FEATURE 4: Streaming Chat ---
@app.post("/chat/stream")
async def chat_stream(req: ChatRequest, request: Request):
    import httpx

    if not check_auth(request):
        return StreamingResponse(
            iter([f"data: {json.dumps({'error': 'Unauthorized'})}\n\n"]),
            media_type="text/event-stream"
        )

    # Learning context
    learning_ctx = get_learning_context()
    enhanced_system = YUUUMIII_SYSTEM
    if learning_ctx:
        enhanced_system = YUUUMIII_SYSTEM + "\n\nUser context: " + learning_ctx

    # URL extraction for web scraper
    enhanced_msg = req.message
    urls = _re.findall(r'https?://[^\s]+', req.message)
    if urls:
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.get(urls[0], headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
                from html.parser import HTMLParser
                class TextExtract(HTMLParser):
                    def __init__(self):
                        super().__init__()
                        self.text = []
                    def handle_data(self, d):
                        self.text.append(d)
                p = TextExtract()
                p.feed(r.text)
                page_text = ' '.join(p.text)[:3000]
                enhanced_msg = req.message + f"\n\n[Webpage content from {urls[0]}]:\n{page_text}"
        except:
            enhanced_msg = req.message

    msgs = []
    for m in conversation_history[-10:]:
        if isinstance(m, dict) and m.get('role') in ('user', 'assistant') and isinstance(m.get('content'), str):
            msgs.append({'role': m['role'], 'content': m['content']})
    msgs.append({'role': 'user', 'content': enhanced_msg})

    async def generate():
        full_reply = ""
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                async with client.stream('POST', f"{OPENCODE_URL}/chat/completions",
                    headers={'Authorization': f'Bearer {OPENCODE_KEY}'},
                    json={'model': YUUUMIII_MODEL, 'messages': [{'role': 'system', 'content': enhanced_system}] + msgs,
                          'max_tokens': 600, 'stream': True}) as r:
                    async for line in r.aiter_lines():
                        if line.startswith('data: '):
                            data = line[6:]
                            if data == '[DONE]':
                                break
                            try:
                                chunk = json.loads(data)
                                delta = chunk['choices'][0]['delta'].get('content', '')
                                if delta:
                                    full_reply += delta
                                    yield f"data: {json.dumps({'delta': delta})}\n\n"
                            except:
                                pass
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

        # Save to history
        if full_reply:
            clean = clean_text(full_reply)
            conversation_history.append({'role': 'user', 'content': req.message, 'time': datetime.datetime.now().strftime('%H:%M')})
            conversation_history.append({'role': 'assistant', 'content': clean, 'time': datetime.datetime.now().strftime('%H:%M')})
            if len(conversation_history) > 20:
                conversation_history[:] = conversation_history[-20:]
            save_history(conversation_history)
            append_memory(req.message, clean, YUUUMIII_MODEL)
            learn_from_conversation(req.message, clean)
        
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/clear")
async def clear():
    conversation_history.clear()
    return {"status": "cleared"}

@app.get("/api/config")
async def get_api_config(request: Request):
    if not check_auth(request):
        return {"error": "Unauthorized"}
    return load_config()

@app.post("/api/config")
async def post_api_config(data: dict, request: Request):
    global YUUUMIII_MODEL
    if not check_auth(request):
        return {"error": "Unauthorized"}
    try:
        existing = load_config()
        existing.update(data)
        # Handle model switching
        if 'selected_model' in data:
            YUUUMIII_MODEL = data['selected_model']
            existing['selected_model'] = YUUUMIII_MODEL
        with open(CONFIG_PATH, 'w') as f:
            json.dump(existing, f, indent=2)
        return {'ok': True}
    except Exception as e:
        return {'ok': False, 'error': str(e)}



# --- NEW API ENDPOINTS (Premium UI) ---

@app.get("/api/system")
async def system_stats():
    return {
        "cpu": psutil.cpu_percent(interval=1),
        "ram": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage('/').percent,
        "uptime": int(psutil.boot_time())
    }

@app.post("/api/terminal")
async def terminal_cmd(data: dict, request: Request):
    import paramiko
    if not check_auth(request):
        return {"error": "Unauthorized"}
    cmd = data.get('cmd', '').strip()[:200]
    if not cmd:
        return {"output": ""}
    blocked = ['rm -rf /', 'mkfs', 'dd if=', 'shutdown', 'reboot', ':(){', 'fork bomb']
    if any(b in cmd for b in blocked):
        return {"output": "Command blocked for safety."}
    vps_pass = os.environ.get('VPS_PASSWORD', 'Wu2Vcvxv')
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect('216.9.227.103', username='root', password=vps_pass, timeout=10)
        stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
        out = stdout.read().decode() + stderr.read().decode()
        client.close()
        return {"output": out.strip()[:2000] or "(no output)"}
    except Exception as e:
        return {"output": f"Error: {str(e)}"}

@app.post("/api/upload")
async def upload_file_api(file: UploadFile = File(...), request: Request = None):
    file_id = str(uuid.uuid4())[:8]
    ext = file.filename.split('.')[-1].lower() if '.' in file.filename else 'bin'
    save_path = f"{UPLOAD_DIR}/{file_id}_{file.filename}"
    content = await file.read()
    with open(save_path, 'wb') as f:
        f.write(content)
    text_exts = ['txt', 'py', 'js', 'html', 'css', 'json', 'md', 'csv']
    file_content = ""
    if ext in text_exts:
        try:
            file_content = content.decode('utf-8')[:3000]
        except:
            file_content = ""
    elif ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
        # Vision/OCR: Ask AI to describe the image
        try:
            import base64
            import httpx as _httpx
            img_b64 = base64.b64encode(content).decode()
            async with _httpx.AsyncClient(timeout=25) as _c:
                _r = await _c.post(f"{OPENCODE_URL}/chat/completions",
                    headers={'Authorization': f'Bearer {OPENCODE_KEY}'},
                    json={'model': 'claude-sonnet-4-5',
                          'messages': [{'role': 'user', 'content': [
                              {'type': 'text', 'text': 'Describe this image in detail. Extract any text visible (OCR). Be thorough.'},
                              {'type': 'image_url', 'image_url': {'url': f'data:image/{ext};base64,{img_b64}'}}
                          ]}], 'max_tokens': 500})
                vision_data = _r.json()
                if 'choices' in vision_data:
                    file_content = vision_data['choices'][0]['message']['content']
        except:
            file_content = f"[Image: {file.filename}]"
    return {
        "file_id": file_id,
        "filename": file.filename,
        "type": ext,
        "size": len(content),
        "content": file_content,
        "is_image": ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']
    }

@app.get("/api/files")
async def list_uploaded_files(request: Request):
    if not check_auth(request):
        return {"error": "Unauthorized"}
    files = []
    if os.path.exists(UPLOAD_DIR):
        for f in sorted(os.listdir(UPLOAD_DIR)):
            fp = os.path.join(UPLOAD_DIR, f)
            if os.path.isfile(fp):
                files.append({"name": f, "size": os.path.getsize(fp)})
    return files



@app.get("/api/models")
async def get_models():
    return {
        "current": YUUUMIII_MODEL,
        "models": {
            "anthropic": ["claude-fable-5","claude-opus-5","claude-opus-4-5","claude-sonnet-5","claude-sonnet-4-5","claude-haiku-4-5"],
            "google": ["gemini-3.6-flash","gemini-3.5-flash","gemini-3.5-flash-lite","gemini-3.1-pro","gemini-3-flash"],
            "openai": ["gpt-5.5","gpt-5.4","gpt-5.2","gpt-5.1","gpt-5","gpt-5.3-codex","gpt-5.1-codex"],
            "xai": ["grok-4.6","grok-4.5","grok-build-0.1"],
            "kimi": ["kimi-k3","kimi-k2.7-code","kimi-k2.6","kimi-k2.5"],
            "deepseek": ["deepseek-v4-pro","deepseek-v4-flash","deepseek-v4-flash-free"],
            "free": ["mimo-v2.5-free","nemotron-3-ultra-free","laguna-s-2.1-free"],
            "other": ["qwen3.6-plus","qwen3.5-plus","glm-5","minimax-m3","minimax-m2.5"]
        }
    }



# ===== LEVEL 4: AI BRAIN ENDPOINTS =====

@app.post("/api/knowledge/add")
async def add_knowledge(data: dict, request: Request):
    if not check_auth(request):
        return {"error": "Unauthorized"}
    title = data.get('title','')
    content_text = data.get('content','')
    if title and content_text:
        save_fact(f'doc:{title}', content_text[:5000])
        brain_save_memory('system', f'[KNOWLEDGE] {title}: {content_text[:500]}', importance=3)
        return {'ok': True, 'title': title}
    return {'ok': False}

@app.get("/api/knowledge")
async def get_knowledge(request: Request):
    if not check_auth(request):
        return {"error": "Unauthorized"}
    facts = get_all_facts()
    docs = [f for f in facts if f['key'].startswith('doc:')]
    return {'docs': docs}

@app.get("/api/memory/stats")
async def memory_stats_api(request: Request):
    if not check_auth(request):
        return {"error": "Unauthorized"}
    return get_memory_stats()

@app.get("/api/memory/search")
async def memory_search_api(request: Request, q: str = ''):
    if not check_auth(request):
        return {"error": "Unauthorized"}
    return {'results': search_memories(q)}

# ===== LEVEL 4: CODE EXECUTION ENGINE =====

@app.post("/api/execute")
async def execute_code(data: dict, request: Request):
    if not check_auth(request):
        return {"error": "Unauthorized"}
    lang = data.get('lang', 'python')
    code = data.get('code', '')

    if not code:
        return {'error': 'No code provided'}

    blocked = ['os.system', 'subprocess', '__import__', 'open(/etc', 'rm -rf', 'shutil.rmtree', 'eval(', 'exec(']
    if any(b in code for b in blocked):
        return {'error': 'Blocked: dangerous code detected', 'output': ''}

    try:
        import subprocess as _sp
        import tempfile as _tf
        suffix = '.py' if lang == 'python' else '.js'
        with _tf.NamedTemporaryFile(mode='w', suffix=suffix, delete=False) as f:
            f.write(code)
            fname = f.name

        if lang == 'python':
            result = _sp.run(['python3', fname], capture_output=True, text=True, timeout=10)
        else:
            result = _sp.run(['node', fname], capture_output=True, text=True, timeout=10)

        os.unlink(fname)
        return {
            'output': (result.stdout + result.stderr).strip()[:2000],
            'exit_code': result.returncode,
            'lang': lang
        }
    except _sp.TimeoutExpired:
        return {'error': 'Timeout (10s)', 'output': ''}
    except Exception as e:
        return {'error': str(e), 'output': ''}

# ===== LEVEL 5: AUTOMATION ENGINE ENDPOINTS =====

@app.get("/api/automation/events")
async def get_automation_events(request: Request):
    if not check_auth(request):
        return {"error": "Unauthorized"}
    return {"events": load_events()}

@app.post("/api/automation/events")
async def save_automation_events(data: dict, request: Request):
    if not check_auth(request):
        return {"error": "Unauthorized"}
    events = data.get('events', [])
    save_events(events)
    return {"ok": True}

@app.post("/api/automation/add")
async def add_automation_event(data: dict, request: Request):
    if not check_auth(request):
        return {"error": "Unauthorized"}
    events = load_events()
    new_event = {
        "id": f"event_{len(events)+1}_{int(_dt.datetime.now().timestamp())}",
        "name": data.get('name', 'Custom Event'),
        "type": data.get('type', 'system'),
        "condition": data.get('condition', ''),
        "action": data.get('action', 'notify'),
        "message": data.get('message', 'Event triggered'),
        "active": True,
        "last_triggered": None,
        "cooldown_minutes": data.get('cooldown', 30)
    }
    events.append(new_event)
    save_events(events)
    return {"ok": True, "event": new_event}

@app.post("/api/automation/toggle/{event_id}")
async def toggle_automation_event(event_id: str, request: Request):
    if not check_auth(request):
        return {"error": "Unauthorized"}
    events = load_events()
    for e in events:
        if e['id'] == event_id:
            e['active'] = not e.get('active', True)
    save_events(events)
    return {"ok": True}


# Start automation engine
start_automator()


# ===== FEATURE: IMAGE GENERATION =====
@app.post("/api/imagine")
async def imagine(data: dict, request: Request):
    import httpx
    if not check_auth(request):
        return {"error": "Unauthorized"}
    prompt = data.get('prompt', '')
    if not prompt:
        return {'error': 'No prompt provided'}
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            # Try image generation first
            try:
                r = await c.post(f"{OPENCODE_URL}/images/generations",
                    headers={'Authorization': f'Bearer {OPENCODE_KEY}'},
                    json={'model': 'dall-e-3', 'prompt': prompt, 'n': 1, 'size': '512x512'})
                if r.status_code == 200 and r.text.strip():
                    d = r.json()
                    if 'data' in d and len(d['data']) > 0:
                        return {'url': d['data'][0].get('url', ''), 'ok': True}
            except:
                pass
            # Fallback: use chat AI to describe
            r2 = await c.post(f"{OPENCODE_URL}/chat/completions",
                headers={'Authorization': f'Bearer {OPENCODE_KEY}'},
                json={'model': YUUUMIII_MODEL,
                      'messages': [{'role': 'user', 'content': f'Create a vivid, detailed visual description of this image concept. Describe it as if painting a picture with words: {prompt}'}],
                      'max_tokens': 400})
            if r2.status_code == 200 and r2.text.strip():
                d2 = r2.json()
                if 'choices' in d2:
                    desc = d2['choices'][0]['message']['content']
                    return {'ok': False, 'description': desc, 'msg': 'Image generation not available via API. Here is a vivid description instead.'}
            return {'ok': False, 'msg': 'Image generation service not available'}
    except Exception as e:
        return {'error': str(e)}


# ===== FEATURE: GITHUB INTEGRATION =====
@app.get("/api/github/repos")
async def github_repos(request: Request):
    import httpx
    if not check_auth(request):
        return {"error": "Unauthorized"}
    cfg = load_config()
    token = cfg.get('github_token', '')
    username = cfg.get('github_username', '')
    if not token:
        return {'error': 'GitHub token not configured. Set it in Config > Integrations.'}
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"https://api.github.com/users/{username}/repos?sort=updated&per_page=10",
                headers={'Authorization': f'token {token}', 'Accept': 'application/vnd.github.v3+json'})
            return {'repos': r.json()}
    except Exception as e:
        return {'error': str(e)}


@app.post("/api/github/create-issue")
async def create_issue(data: dict, request: Request):
    import httpx
    if not check_auth(request):
        return {"error": "Unauthorized"}
    cfg = load_config()
    token = cfg.get('github_token', '')
    repo = data.get('repo', '')
    title = data.get('title', '')
    body = data.get('body', '')
    if not token or not repo:
        return {'error': 'GitHub token or repo not configured'}
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(f"https://api.github.com/repos/{repo}/issues",
                headers={'Authorization': f'token {token}', 'Accept': 'application/vnd.github.v3+json'},
                json={'title': title, 'body': body})
            return r.json()
    except Exception as e:
        return {'error': str(e)}


@app.get("/api/github/activity")
async def github_activity(request: Request):
    import httpx
    if not check_auth(request):
        return {"error": "Unauthorized"}
    cfg = load_config()
    token = cfg.get('github_token', '')
    username = cfg.get('github_username', '')
    if not token:
        return {'error': 'GitHub not configured'}
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"https://api.github.com/users/{username}/events?per_page=10",
                headers={'Authorization': f'token {token}', 'Accept': 'application/vnd.github.v3+json'})
            events = r.json()
            summary = []
            if isinstance(events, list):
                for e in events[:5]:
                    t = e.get('type', '')
                    repo = e.get('repo', {}).get('name', '')
                    summary.append(f"{t} on {repo}")
            return {'activity': summary, 'raw': events[:5] if isinstance(events, list) else []}
    except Exception as e:
        return {'error': str(e)}


# ===== FEATURE: INVOICE GENERATOR =====
@app.post("/api/invoice")
async def generate_invoice(data: dict, request: Request):
    import time as _time
    import datetime as _datetime
    if not check_auth(request):
        return {"error": "Unauthorized"}
    client_name = data.get('client', 'Client')
    amount = data.get('amount', 0)
    items = data.get('items', [])
    invoice_id = f"INV-{int(_time.time())}"
    date_str = _datetime.datetime.now().strftime('%Y-%m-%d')

    items_html = ""
    for i in items:
        name = i.get('name', 'Item')
        qty = i.get('qty', 1)
        price = i.get('price', 0)
        total = qty * price
        items_html += f"<tr><td>{name}</td><td>{qty}</td><td>Rs.{price}</td><td>Rs.{total}</td></tr>"

    if not items_html:
        items_html = f"<tr><td>Service</td><td>1</td><td>Rs.{amount}</td><td>Rs.{amount}</td></tr>"

    html = f"""<!DOCTYPE html>
<html><head><style>
body{{font-family:Arial,sans-serif;max-width:700px;margin:40px auto;color:#333}}
.header{{background:#000;color:#00f5ff;padding:30px;text-align:center}}
h1{{margin:0;font-size:2rem;letter-spacing:6px}}
.meta{{display:flex;justify-content:space-between;padding:20px;border-bottom:1px solid #eee}}
table{{width:100%;border-collapse:collapse;margin:20px 0}}
th{{background:#f5f5f5;padding:10px;text-align:left}}
td{{padding:10px;border-bottom:1px solid #eee}}
.total{{text-align:right;font-size:1.2rem;font-weight:bold;padding:20px}}
.footer{{text-align:center;color:#888;font-size:0.8rem;margin-top:30px}}
</style></head><body>
<div class="header"><h1>INVOICE</h1><div style="color:#fff;margin-top:5px">YUUUMIII PLATFORM</div></div>
<div class="meta">
  <div><strong>Invoice:</strong> {invoice_id}<br><strong>Date:</strong> {date_str}</div>
  <div><strong>Bill To:</strong><br>{client_name}</div>
</div>
<table><tr><th>Item</th><th>Qty</th><th>Price</th><th>Total</th></tr>
{items_html}
</table>
<div class="total">Total: Rs.{amount}</div>
<div class="footer">Generated by Yuuumiii AI Platform - {date_str}</div>
</body></html>"""

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    path = f"{UPLOAD_DIR}/invoice_{invoice_id}.html"
    with open(path, 'w') as f:
        f.write(html)
    return {'ok': True, 'invoice_id': invoice_id, 'path': f'/invoice/{invoice_id}'}


@app.get("/invoice/{invoice_id}")
async def view_invoice(invoice_id: str):
    from pathlib import Path
    path = f"{UPLOAD_DIR}/invoice_{invoice_id}.html"
    if Path(path).exists():
        return HTMLResponse(Path(path).read_text())
    return HTMLResponse("<h1>Invoice not found</h1>", status_code=404)


# ===== FEATURE: CRM BASIC =====
CRM_FILE = '/root/daxx-assistant/crm.json'

def load_crm():
    from pathlib import Path
    if Path(CRM_FILE).exists():
        try:
            return json.loads(Path(CRM_FILE).read_text())
        except:
            return []
    return []

def save_crm(data):
    with open(CRM_FILE, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

@app.get("/api/crm")
async def get_crm(request: Request):
    if not check_auth(request):
        return {"error": "Unauthorized"}
    return {"contacts": load_crm()}

@app.post("/api/crm")
async def add_contact(data: dict, request: Request):
    import datetime as _dt
    if not check_auth(request):
        return {"error": "Unauthorized"}
    crm = load_crm()
    contact = {
        "id": (max([c.get('id', 0) for c in crm]) + 1) if crm else 1,
        "name": data.get('name', ''),
        "email": data.get('email', ''),
        "phone": data.get('phone', ''),
        "notes": data.get('notes', ''),
        "added": _dt.datetime.now().isoformat(),
        "follow_up": data.get('follow_up', '')
    }
    crm.append(contact)
    save_crm(crm)
    return {"ok": True, "contact": contact}

@app.delete("/api/crm/{contact_id}")
async def delete_contact(contact_id: int, request: Request):
    if not check_auth(request):
        return {"error": "Unauthorized"}
    crm = load_crm()
    crm = [c for c in crm if c.get('id') != contact_id]
    save_crm(crm)
    return {"ok": True}


def run_server(host="0.0.0.0", port=8080):
    print(f"\n Web UI starting at http://{host}:{port}\n")
    uvicorn.run(app, host=host, port=port, log_level="info")

@app.get("/api/history")
async def get_history(request: Request):
    if not check_auth(request):
        return {"error": "Unauthorized"}
    return {"history": conversation_history, "count": len(conversation_history)}

@app.delete("/api/history")
async def delete_history(request: Request):
    if not check_auth(request):
        return {"error": "Unauthorized"}
    conversation_history.clear()
    if os.path.exists(HISTORY_FILE):
        os.remove(HISTORY_FILE)
    return {"ok": True}

@app.get("/api/memory")
async def get_memory(request: Request):
    if not check_auth(request):
        return {"error": "Unauthorized"}
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, encoding='utf-8') as f:
            return {"memory": f.read(), "size": os.path.getsize(MEMORY_FILE)}
    return {"memory": "", "size": 0}

@app.delete("/api/memory")
async def clear_memory(request: Request):
    if not check_auth(request):
        return {"error": "Unauthorized"}
    if os.path.exists(MEMORY_FILE):
        os.remove(MEMORY_FILE)
    return {"ok": True}
