import json, os

CONFIG_FILE = os.path.expanduser("~/.assistant_config.json")

DEFAULTS = {
    "opencode_api_key": "",
    "claude_api_key": "",
    "ai_provider": "opencode",
    "model": "claude-sonnet-4-5",
    "opencode_base_url": "https://opencode.ai/zen/v1",
    "voice_enabled": False,
    "voice_speed": 150,
    "email_address": "",
    "email_password": "",
    "email_smtp": "smtp.gmail.com",
    "email_imap": "imap.gmail.com",
    "github_token": "",
    "web_port": 8080,
    "web_host": "0.0.0.0",
    "username": "DAXX"
}

def load() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
        return {**DEFAULTS, **cfg}
    return DEFAULTS.copy()

def save(data: dict):
    cfg = load()
    cfg.update(data)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f, indent=2)
    return cfg

def get(key: str, default=None):
    return load().get(key, default or DEFAULTS.get(key, ""))
