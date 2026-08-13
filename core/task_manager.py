import uuid
import time
from typing import Optional

class TaskManager:
    def __init__(self):
        self.tasks = {}

    def add_task(self, title: str) -> str:
        task_id = str(uuid.uuid4())[:8]
        self.tasks[task_id] = {
            "id": task_id,
            "title": title,
            "status": "pending",
            "progress": 0,
            "result": None,
            "created_at": time.time(),
            "updated_at": time.time(),
            "logs": []
        }
        return task_id

    def update_task(self, task_id: str, status: Optional[str] = None, progress: Optional[int] = None, log: Optional[str] = None, result: Optional[str] = None):
        if task_id not in self.tasks:
            return
        task = self.tasks[task_id]
        if status:
            task["status"] = status
        if progress is not None:
            task["progress"] = progress
        if log:
            task["logs"].append(log)
        if result is not None:
            task["result"] = result
        task["updated_at"] = time.time()

    def get_task(self, task_id: str) -> Optional[dict]:
        return self.tasks.get(task_id)

    def get_all_tasks(self) -> list:
        return sorted(self.tasks.values(), key=lambda x: x["created_at"], reverse=True)

    def cancel_task(self, task_id: str) -> bool:
        if task_id in self.tasks and self.tasks[task_id]["status"] in ("pending", "running"):
            self.tasks[task_id]["status"] = "failed"
            self.tasks[task_id]["logs"].append("Task cancelled by user")
            self.tasks[task_id]["updated_at"] = time.time()
            return True
        return False

task_manager = TaskManager()
