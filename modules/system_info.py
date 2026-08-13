def get_info() -> str:
    try:
        import psutil, platform
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        return (
            f"OS: {platform.system()} {platform.release()}\n"
            f"CPU: {cpu}%\n"
            f"RAM: {ram.used // 1024 // 1024}MB / {ram.total // 1024 // 1024}MB ({ram.percent}%)\n"
            f"Disk: {disk.used // 1024 // 1024 // 1024}GB / {disk.total // 1024 // 1024 // 1024}GB ({disk.percent}%)"
        )
    except ImportError:
        import platform, os
        return f"OS: {platform.system()} {platform.release()}\n(psutil not installed for detailed stats)"
    except Exception as e:
        return f"Error: {e}"
