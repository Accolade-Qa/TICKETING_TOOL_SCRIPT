import csv
import json
from pathlib import Path


def write_json(results, path):
    Path(path).write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")


def write_csv(results, path):
    fields = ["name", "expected", "http_status", "ticket_number", "record_status", "passed", "duration_ms", "exception"]
    with Path(path).open("w", newline="", encoding="utf-8") as report_file:
        writer = csv.DictWriter(report_file, fieldnames=fields)
        writer.writeheader()
        for result in results:
            writer.writerow({field: result.get(field, "") for field in fields})
