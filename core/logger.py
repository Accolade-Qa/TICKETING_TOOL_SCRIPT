import json
from datetime import datetime, timezone
from pathlib import Path


class RunLogger:
    def __init__(self, log_directory="logs/runs"):
        self.directory = Path(log_directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        filename = datetime.now().strftime("%Y-%m-%d_%H%M%S.jsonl")
        self.path = self.directory / filename

    def write(self, result):
        with self.path.open("a", encoding="utf-8") as log_file:
            entry = {"timestamp": datetime.now(timezone.utc).isoformat(), **result}
            log_file.write(json.dumps(entry, default=str) + "\n")
