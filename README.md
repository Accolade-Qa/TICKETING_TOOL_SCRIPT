# CRM Ticket Testing Utility

This utility generates CRM ticket payloads, runs registered scenarios, validates API responses, and logs every execution.

## Setup

```powershell
python -m pip install -r requirements.txt
```

Keep API settings in a local `.env` file. Do not commit that file.

## Single entry point

```powershell
python main.py
```

The PyQt6 window supports scenario filtering, running one or all scenarios, progress tracking, generated payload and raw response inspection, validation details, and JSON/CSV export.

Use the same entry point for command-line execution:

Run one scenario:

```powershell
python main.py --cli --scenario test_vin_no_valid_format --export json
```

Run all registered scenarios:

```powershell
python main.py --cli --all --export csv
```

Every run writes JSONL records to `logs/runs`. Reports are written to `logs/reports`.

## Project layout

- `main.py`: single application entry point for desktop and CLI modes
- `scenarios/ticket_scenarios.py`: scenario definitions and registry
- `core/`: reusable payload, API, validation, runner, logging, and reporting services
- `ui/main_window.py`: desktop window implementation used by `main.py`
- `data/payload.json`: base ticket payload
- `tests/`: offline tests that do not call the CRM API
