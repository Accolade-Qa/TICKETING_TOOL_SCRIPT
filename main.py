import argparse
from pathlib import Path

from core.logger import RunLogger
from core.reports import write_csv, write_json
from core.runner import ScenarioRunner
from scenarios import SCENARIO_FUNCTIONS


def run_cli(scenario_name=None, run_all=False, export_format=None):
    if scenario_name:
        selected = [
            function
            for function in SCENARIO_FUNCTIONS
            if function.__name__ == scenario_name
        ]
        if not selected:
            raise ValueError(f"Unknown scenario: {scenario_name}")
    elif run_all:
        selected = SCENARIO_FUNCTIONS
    else:
        raise ValueError("Choose --scenario NAME or --all")

    runner = ScenarioRunner(run_logger=RunLogger())
    results = []
    for function in selected:
        result = runner.run_function(function)
        results.append(result)
        status = "PASS" if result.get("passed") else "FAIL"
        print(
            f"{status:<4} {result['name']} | "
            f"HTTP={result.get('http_status')} | {result.get('duration_ms')} ms"
        )
        if result.get("exception"):
            print(f"     {result['exception']}")

    passed = sum(1 for result in results if result.get("passed"))
    print(f"\nSummary: {passed}/{len(results)} passed")
    if export_format:
        output_directory = Path("logs/reports")
        output_directory.mkdir(parents=True, exist_ok=True)
        report_path = output_directory / f"scenario_results.{export_format}"
        if export_format == "json":
            write_json(results, report_path)
        else:
            write_csv(results, report_path)
        print(f"Report: {report_path}")
    return results


def main():
    parser = argparse.ArgumentParser(description="CRM ticket testing utility")
    parser.add_argument("--cli", action="store_true", help="Run without the desktop UI")
    parser.add_argument("--scenario", help="Exact scenario function name")
    parser.add_argument("--all", action="store_true", help="Run all registered scenarios")
    parser.add_argument("--export", choices=["json", "csv"], help="Export CLI results")
    args = parser.parse_args()

    if args.cli or args.scenario or args.all:
        try:
            run_cli(args.scenario, args.all, args.export)
        except ValueError as error:
            parser.error(str(error))
        return

    from PyQt6.QtWidgets import QApplication
    from ui import TicketScenarioWindow

    application = QApplication([])
    window = TicketScenarioWindow()
    window.show()
    application.exec()


if __name__ == "__main__":
    main()
