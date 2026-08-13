import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run():
    print("\n🤖 AI Assistant Setup\n" + "=" * 40)
    from config.settings import load, save

    cfg = load()

    print("\n1. AI Provider")
    print("   [1] OpenCode AI (60+ models) - recommended")
    print("   [2] Claude API (direct)")
    choice = input("Choose [1/2]: ").strip() or "1"
    provider = "opencode" if choice == "1" else "claude"

    if provider == "opencode":
        key = input("\nOpenCode API Key (opencode.ai): ").strip()
        save({"ai_provider": "opencode", "opencode_api_key": key})

        print("\nModel (press Enter for default):")
        print("  claude-sonnet-4-5 (default)")
        print("  kimi-k2.7-code | kimi-k3 | gpt-5.5 | deepseek-v4-pro | gemini-3.5-flash")
        model = input("Model: ").strip() or "claude-sonnet-4-5"
    else:
        key = input("\nClaude API Key (console.anthropic.com): ").strip()
        model = "claude-3-5-haiku-20241022"
        save({"ai_provider": "claude", "claude_api_key": key, "opencode_base_url": "https://api.anthropic.com/v1"})

    save({"model": model})

    print("\n2. Your Name")
    name = input("Your name [DAXX]: ").strip() or "DAXX"
    save({"username": name})

    print("\n3. Email (optional, for send/receive)")
    email = input("Gmail address (Enter to skip): ").strip()
    if email:
        pw = input("App password (Gmail > App Passwords): ").strip()
        save({"email_address": email, "email_password": pw})

    print("\n4. GitHub Token (optional)")
    gh = input("GitHub token (Enter to skip): ").strip()
    if gh:
        save({"github_token": gh})

    print("\n✅ Setup complete!")
    print("\nRun:")
    print("  python main.py        → Terminal mode")
    print("  python main.py --web  → Web UI mode\n")


if __name__ == "__main__":
    run()
