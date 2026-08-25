from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScenarioResult:
    name: str
    expected: str = "unknown"
    object_count: int = 1
    http_status: int | None = None
    response_json: Any = None
    response_text: str = ""
    payload: Any = None
    passed: bool = False
    ticket_number: str | None = None
    record_message: str | None = None
    record_status: str | None = None
    validation_errors: list[str] = field(default_factory=list)
    expected_record_message: str | None = None
    expected_validation_errors: list[str] = field(default_factory=list)
    expected_response_json: Any = None
    duration_ms: float | None = None
    exception: str | None = None

    def to_dict(self):
        return {
            key: value for key, value in self.__dict__.items()
        }
