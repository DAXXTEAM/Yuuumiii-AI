import json, os
from pathlib import Path

PREFS_FILE = '/root/daxx-assistant/user_prefs.json'
LEARN_FILE = '/root/daxx-assistant/learned_facts.json'

def load_prefs():
    if Path(PREFS_FILE).exists():
        try:
            return json.loads(Path(PREFS_FILE).read_text())
        except:
            pass
    return {"language": "hindi", "name": "DAXX", "preferences": [], "frequent_tasks": {}}

def save_prefs(prefs):
    Path(PREFS_FILE).write_text(json.dumps(prefs, ensure_ascii=False, indent=2))

def learn_from_conversation(user_msg, ai_reply):
    prefs = load_prefs()
    
    # Detect language preference
    hindi_words = ['karo', 'hai', 'kya', 'nahi', 'tha', 'hoon', 'aap', 'mera', 'isko']
    if any(w in user_msg.lower() for w in hindi_words):
        prefs['language'] = 'hindi'
    
    # Track frequent task types
    task_keywords = {
        'code': ['code', 'script', 'function', 'bug', 'error'],
        'vps': ['pm2', 'server', 'restart', 'deploy', 'nginx'],
        'email': ['email', 'mail', 'send'],
        'research': ['search', 'find', 'research', 'kya hai'],
    }
    for task, keywords in task_keywords.items():
        if any(k in user_msg.lower() for k in keywords):
            prefs['frequent_tasks'][task] = prefs['frequent_tasks'].get(task, 0) + 1
    
    save_prefs(prefs)
    return prefs

def get_learning_context():
    prefs = load_prefs()
    top_tasks = sorted(prefs.get('frequent_tasks', {}).items(), key=lambda x: x[1], reverse=True)[:3]
    ctx = f"User name: {prefs.get('name', 'DAXX')}. Language: {prefs.get('language', 'hindi')}."
    if top_tasks:
        ctx += f" Frequent tasks: {', '.join([t[0] for t in top_tasks])}."
    return ctx
