"""Format AI responses for terminal/web output"""

def format_terminal(text: str) -> str:
    """Format response for terminal display"""
    if not text:
        return ""
    return text

def format_web(text: str) -> str:
    """Format response for web display (keep markdown)"""
    if not text:
        return ""
    return text
