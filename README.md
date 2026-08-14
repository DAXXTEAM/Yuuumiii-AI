# Yuuumiii AI

Premium open-source AI assistant with cyberpunk UI.
Built with FastAPI + SQLite + Telegram integration.

## Live Demo

- Web UI: https://novels-tide-tue-aging.trycloudflare.com
- Password: `yuuumiii2025`

## Features

- AI Chat (Claude Sonnet)
- VPS Terminal
- Task Manager
- CRM
- Config Panel
- Telegram Bot
- Voice Assistant

## Run

```bash
pip install -r requirements.txt
python main.py --web
```

## Deploy

```bash
PORT=8080 pm2 start main.py --name Yuuumiii-AI --interpreter python3 -- --web
```
