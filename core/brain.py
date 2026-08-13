import sqlite3, json, datetime, os
from pathlib import Path

DB_PATH = '/root/daxx-assistant/yuuumiii_brain.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT,
            content TEXT,
            summary TEXT,
            timestamp TEXT,
            tags TEXT,
            importance INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE,
            value TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS tasks_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            status TEXT,
            result TEXT,
            created_at TEXT,
            completed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            trigger_type TEXT,
            condition TEXT,
            action TEXT,
            last_checked TEXT,
            active INTEGER DEFAULT 1
        );
    ''')
    conn.commit()
    conn.close()

def save_memory(role, content, importance=1):
    ts = datetime.datetime.now().isoformat()
    tags = extract_tags(content)
    conn = sqlite3.connect(DB_PATH)
    conn.execute('INSERT INTO memories (role,content,timestamp,tags,importance) VALUES (?,?,?,?,?)',
                 (role, content[:2000], ts, tags, importance))
    conn.commit()
    conn.close()

def extract_tags(text):
    keywords = ['code','vps','email','github','task','pm2','server','bot','python','js']
    found = [k for k in keywords if k in text.lower()]
    return ','.join(found)

def get_recent_memories(limit=20):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute('SELECT role,content,timestamp FROM memories ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
    conn.close()
    return [{'role':r[0],'content':r[1],'time':r[2]} for r in reversed(rows)]

def search_memories(query, limit=5):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute('SELECT role,content,timestamp FROM memories WHERE content LIKE ? ORDER BY importance DESC LIMIT ?',
                        (f'%{query}%', limit)).fetchall()
    conn.close()
    return [{'role':r[0],'content':r[1],'time':r[2]} for r in rows]

def save_fact(key, value):
    ts = datetime.datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    conn.execute('INSERT OR REPLACE INTO facts (key,value,updated_at) VALUES (?,?,?)', (key,value,ts))
    conn.commit()
    conn.close()

def get_fact(key):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute('SELECT value FROM facts WHERE key=?', (key,)).fetchone()
    conn.close()
    return row[0] if row else None

def get_all_facts():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute('SELECT key,value,updated_at FROM facts').fetchall()
    conn.close()
    return [{'key':r[0],'value':r[1],'updated':r[2]} for r in rows]

def get_memory_stats():
    conn = sqlite3.connect(DB_PATH)
    total = conn.execute('SELECT COUNT(*) FROM memories').fetchone()[0]
    facts = conn.execute('SELECT COUNT(*) FROM facts').fetchone()[0]
    conn.close()
    return {'total_memories': total, 'facts': facts}

init_db()
