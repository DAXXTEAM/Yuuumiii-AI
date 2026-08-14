import requests, json
from config.settings import get, load

TOOLS = [
    {"type":"function","function":{"name":"web_search","description":"Search the web for information, news, companies, clients","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
    {"type":"function","function":{"name":"fetch_url","description":"Fetch and read content from any URL","parameters":{"type":"object","properties":{"url":{"type":"string"}},"required":["url"]}}},
    {"type":"function","function":{"name":"find_clients","description":"Find potential clients or companies in a specific industry/location","parameters":{"type":"object","properties":{"industry":{"type":"string"},"location":{"type":"string","default":"India"},"type":{"type":"string","enum":["clients","companies","leads"],"default":"clients"}},"required":["industry"]}}},
    {"type":"function","function":{"name":"send_email","description":"Send an email","parameters":{"type":"object","properties":{"to":{"type":"string"},"subject":{"type":"string"},"body":{"type":"string"}},"required":["to","subject","body"]}}},
    {"type":"function","function":{"name":"read_emails","description":"Read recent emails from inbox","parameters":{"type":"object","properties":{"count":{"type":"integer","default":5}}}}},
    {"type":"function","function":{"name":"run_code","description":"Execute Python or bash code","parameters":{"type":"object","properties":{"language":{"type":"string","enum":["python","bash"]},"code":{"type":"string"}},"required":["language","code"]}}},
    {"type":"function","function":{"name":"read_file","description":"Read a file from local system","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}},
    {"type":"function","function":{"name":"write_file","description":"Write content to a file","parameters":{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}}},
    {"type":"function","function":{"name":"list_files","description":"List files in a directory","parameters":{"type":"object","properties":{"path":{"type":"string","default":"."}}}}},
    {"type":"function","function":{"name":"system_info","description":"Get system information - CPU, RAM, disk, OS","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"calculator","description":"Calculate math expressions","parameters":{"type":"object","properties":{"expression":{"type":"string"}},"required":["expression"]}}},
    {"type":"function","function":{"name":"weather","description":"Get weather for a city","parameters":{"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}}},
    {"type":"function","function":{"name":"currency_convert","description":"Convert currency","parameters":{"type":"object","properties":{"amount":{"type":"number"},"from_currency":{"type":"string"},"to_currency":{"type":"string"}},"required":["amount","from_currency","to_currency"]}}},
]

SYSTEM = """You are an advanced AI assistant for a tech company CEO named {username}.

Your capabilities:
- Find clients, leads, and companies for their tech business
- Send and read emails professionally
- Search the web for market research and competitor analysis
- Run code and analyze data
- Manage files and projects
- Answer any technical or business questions

Always be professional, concise, and action-oriented.
When finding clients, search multiple sources and provide actionable contact info.
Reply in the same language as the user."""


class Agent:
    def __init__(self):
        self.cfg = load()

    def _get_system(self):
        if hasattr(self, '_system_override') and self._system_override:
            return self._system_override
        return SYSTEM.format(username=get("username", "DAXX"))

    def _call_api(self, messages, tools=True):
        provider = get("ai_provider")
        key = get("opencode_api_key") if provider == "opencode" else get("claude_api_key")
        base = get("opencode_base_url") if provider == "opencode" else "https://api.anthropic.com/v1"
        model = get("model")

        if not key:
            raise Exception("API key not set. Run: python main.py --setup")

        payload = {"model": model, "messages": messages, "max_tokens": 2048}
        if tools and provider != "opencode":
            payload["tools"] = TOOLS
            payload["tool_choice"] = "auto"

        r = requests.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload, timeout=60
        )
        if r.status_code != 200:
            raise Exception(f"API Error {r.status_code}: {r.text[:200]}")
        return r.json()

    def run(self, user_message: str, history: list = None, on_tool=None) -> tuple:
        """Returns (response_text, updated_history)"""
        messages = [{"role": "system", "content": self._get_system()}]
        if history:
            messages.extend(history[-10:])
        messages.append({"role": "user", "content": user_message})

        from modules import web_search, email_mod, client_finder, files, code_runner, system_info

        def execute_tool(name, args):
            if name == "web_search":
                return web_search.search(args["query"])
            elif name == "fetch_url":
                return web_search.fetch(args["url"])
            elif name == "find_clients":
                return client_finder.find(args["industry"], args.get("location", "India"), args.get("type", "clients"))
            elif name == "send_email":
                return email_mod.send(args["to"], args["subject"], args["body"])
            elif name == "read_emails":
                return email_mod.read(args.get("count", 5))
            elif name == "run_code":
                return code_runner.run(args["language"], args["code"])
            elif name == "read_file":
                return files.read(args["path"])
            elif name == "write_file":
                return files.write(args["path"], args["content"])
            elif name == "list_files":
                return files.list_dir(args.get("path", "."))
            elif name == "system_info":
                return system_info.get_info()
            elif name == "calculator":
                import ast
                expr = args["expression"].replace("^", "**")
                return f"{expr} = {eval(compile(ast.parse(expr, mode='eval'), '<s>', 'eval'))}"
            elif name == "weather":
                r = requests.get(f"https://wttr.in/{args['city']}?format=j1", timeout=8).json()
                c = r["current_condition"][0]
                return f"Temp: {c['temp_C']}°C | {c['weatherDesc'][0]['value']} | Humidity: {c['humidity']}%"
            elif name == "currency_convert":
                r = requests.get(f"https://open.er-api.com/v6/latest/{args['from_currency'].upper()}", timeout=8).json()
                rate = r["rates"][args["to_currency"].upper()]
                return f"{args['amount']} {args['from_currency'].upper()} = {float(args['amount'])*rate:.2f} {args['to_currency'].upper()}"
            return f"Unknown tool: {name}"

        for _ in range(8):
            data = self._call_api(messages)
            choice = data["choices"][0]
            msg = choice["message"]

            if not msg.get("tool_calls") or choice.get("finish_reason") == "stop":
                new_history = [m for m in messages if m["role"] != "system"]
                return msg.get("content", "Done."), new_history

            messages.append({"role": "assistant", "content": msg.get("content", ""), "tool_calls": msg["tool_calls"]})

            for tc in msg["tool_calls"]:
                name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"])
                except (json.JSONDecodeError, KeyError):
                    args = {}
                if on_tool:
                    on_tool(name, args)
                result = execute_tool(name, args)
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": str(result)})

        new_history = [m for m in messages if m["role"] != "system"]
        return "Task completed.", new_history
