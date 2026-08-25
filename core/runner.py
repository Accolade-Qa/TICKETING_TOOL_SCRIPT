import time

from .api_client import ApiClient
from .logger import RunLogger
from .models import ScenarioResult
from .validator import validate_response


class ScenarioRunner:
    def __init__(self, api_client=None, run_logger=None):
        self.api_client = api_client or ApiClient()
        self.run_logger = run_logger or RunLogger()

    def run_function(self, scenario_function):
        started = time.perf_counter()
        try:
            raw_result = scenario_function()
            result = ScenarioResult(**{
                key: raw_result.get(key)
                for key in ScenarioResult.__dataclass_fields__
                if key in raw_result
            })
            result_dict = result.to_dict()
        except Exception as error:
            result_dict = ScenarioResult(
                name=scenario_function.__name__,
                exception=f"{type(error).__name__}: {error}",
            ).to_dict()
        result_dict["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
        self.run_logger.write(result_dict)
        return result_dict

    def run_functions(self, scenario_functions):
        return [self.run_function(function) for function in scenario_functions]

    def run_payload(self, name, payload_list, expected="unknown", **expectations):
        started = time.perf_counter()
        try:
            api_result = self.api_client.send(payload_list)
            validation = validate_response(api_result, expected, **expectations)
            result = ScenarioResult(
                name=name, expected=expected, object_count=len(payload_list),
                payload=payload_list, **api_result, **validation,
            ).to_dict()
        except Exception as error:
            result = ScenarioResult(
                name=name, expected=expected, object_count=len(payload_list),
                payload=payload_list, exception=f"{type(error).__name__}: {error}",
            ).to_dict()
        result["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
        self.run_logger.write(result)
        return result
