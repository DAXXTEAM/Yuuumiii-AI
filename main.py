#!/usr/bin/env python3
import sys, os

# Ensure the assistant directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_setup():
    from setup_wizard import run
    run()


def run_terminal():
    from core.agent import Agent
    from config.settings import get

    agent = Agent()
    history = []
    name = get("username", "User")
    model = get("model", "claude-sonnet-4-5")

    print(f"\n🤖 AI Assistant (model: {model})")
    print(f"👋 Hello {name}! Type your message. Ctrl+C to exit.\n")
    print("Commands: /clear (reset history) | /model <name> | /exit\n")

    while True:
        try:
            user_input = input("You > ").strip()
            if not user_input:
                continue

            if user_input == "/exit":
                break
            elif user_input == "/clear":
                history = []
                print("✅ History cleared.\n")
                continue
            elif user_input.startswith("/model "):
                from config.settings import save
                new_model = user_input.split(" ", 1)[1]
                save({"model": new_model})
                model = new_model
                print(f"✅ Model: {model}\n")
                continue

            print("⚙️ Thinking", end="", flush=True)

            def on_tool(name, args):
                print(f"\r🔧 {name}...", end="", flush=True)

            try:
                response, history = agent.run(user_input, history, on_tool=on_tool)
                print(f"\r\nAssistant > {response}\n")
            except Exception as e:
                print(f"\r\n❌ Error: {e}\n")

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except EOFError:
            print("\n\nGoodbye!")
            break


def run_web():
    from web.server import run_server
    port = int(os.environ.get("PORT", 8080))
    host = "0.0.0.0"
    print(f"\n🌐 Web UI starting at http://{host}:{port}")
    print(f"Access from anywhere: http://YOUR_VPS_IP:{port}\n")
    run_server(host=host, port=port)


if __name__ == "__main__":
    if "--setup" in sys.argv:
        run_setup()
    elif "--web" in sys.argv:
        run_web()
    else:
        if len(sys.argv) == 1:
            run_terminal()
        else:
            print("Usage:")
            print("  python main.py          # terminal mode")
            print("  python main.py --web    # web UI mode")
            print("  python main.py --setup  # configure settings")
