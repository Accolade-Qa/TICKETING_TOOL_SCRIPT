import json
import tempfile
import unittest
from pathlib import Path

from core.logger import RunLogger
from core.payload_generator import build_payload
from core.reports import write_csv, write_json
from core.validator import validate_response


class CoreTests(unittest.TestCase):
    def test_payload_generates_unique_vin_suffix(self):
        payload = build_payload({"VIN_NO": "MAT0000"}, {})
        self.assertRegex(payload["VIN_NO"], r"^MAT\d{4}$")

    def test_accept_response(self):
        result = validate_response(
            {"http_status": 201, "response_json": {"data": [{"message": "Data Saved Successfully!!", "status": "SUCCESS"}]}},
            expected="accept",
        )
        self.assertTrue(result["passed"])

    def test_reject_response_with_validation_error(self):
        result = validate_response(
            {"http_status": 200, "response_json": {"data": [{"VALIDATION_ERROR": ["VIN is invalid"]}]}},
            expected="reject",
        )
        self.assertTrue(result["passed"])
        self.assertEqual(result["validation_errors"], ["VIN is invalid"])

    def test_logger_and_reports(self):
        with tempfile.TemporaryDirectory() as directory:
            logger = RunLogger(directory)
            logger.write({"name": "demo", "passed": True})
            self.assertTrue(Path(logger.path).exists())
            results = [{"name": "demo", "passed": True}]
            json_path = Path(directory) / "results.json"
            csv_path = Path(directory) / "results.csv"
            write_json(results, json_path)
            write_csv(results, csv_path)
            self.assertEqual(json.loads(json_path.read_text())[0]["name"], "demo")
            self.assertTrue(csv_path.exists())


if __name__ == "__main__":
    unittest.main()
