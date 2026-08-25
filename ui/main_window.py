import json
from pathlib import Path

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.logger import RunLogger
from core.reports import write_csv, write_json
from core.runner import ScenarioRunner
from scenarios import SCENARIO_FUNCTIONS


class WorkerSignals(QObject):
    result = pyqtSignal(object)
    error = pyqtSignal(str)
    finished = pyqtSignal()


class ScenarioWorker(QRunnable):
    def __init__(self, runner, scenario_function):
        super().__init__()
        self.runner = runner
        self.scenario_function = scenario_function
        self.signals = WorkerSignals()

    def run(self):
        try:
            self.signals.result.emit(self.runner.run_function(self.scenario_function))
        except Exception as error:
            self.signals.error.emit(f"{type(error).__name__}: {error}")
        finally:
            self.signals.finished.emit()


class TicketScenarioWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.thread_pool = QThreadPool.globalInstance()
        self.runner = ScenarioRunner(run_logger=RunLogger())
        self.all_functions = list(SCENARIO_FUNCTIONS)
        self.visible_functions = list(self.all_functions)
        self.results = []
        self.running = 0
        self.setWindowTitle("CRM Ticket Testing Utility")
        self.resize(1280, 780)
        self.build_ui()
        self.apply_style()

    def build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        title = QLabel("CRM Ticket Testing Utility")
        title.setObjectName("title")
        subtitle = QLabel("Generate, execute, validate, and audit ticket scenarios")
        subtitle.setObjectName("subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        controls = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter scenarios...")
        self.search.textChanged.connect(self.filter_scenarios)
        self.scenario_picker = QComboBox()
        self.run_selected_button = QPushButton("Run selected")
        self.run_selected_button.clicked.connect(self.run_selected)
        self.run_all_button = QPushButton("Run all")
        self.run_all_button.clicked.connect(self.run_all)
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_results)
        self.export_button = QPushButton("Export")
        self.export_button.clicked.connect(self.export_results)
        controls.addWidget(self.search, 2)
        controls.addWidget(self.scenario_picker, 3)
        controls.addWidget(self.run_selected_button)
        controls.addWidget(self.run_all_button)
        controls.addWidget(self.clear_button)
        controls.addWidget(self.export_button)
        layout.addLayout(controls)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setFormat("Ready")
        layout.addWidget(self.progress)

        self.results_table = QTableWidget(0, 7)
        self.results_table.setHorizontalHeaderLabels(
            ["Scenario", "Expected", "HTTP", "Ticket", "Status", "Duration", "Result"]
        )
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results_table.itemSelectionChanged.connect(self.show_selected_result)
        self.results_table.horizontalHeader().setStretchLastSection(True)

        self.details = QTabWidget()
        self.request_view = QPlainTextEdit()
        self.response_view = QPlainTextEdit()
        self.validation_view = QPlainTextEdit()
        for view in (self.request_view, self.response_view, self.validation_view):
            view.setReadOnly(True)
        self.details.addTab(self.request_view, "Generated payload")
        self.details.addTab(self.response_view, "Raw response")
        self.details.addTab(self.validation_view, "Validation")

        splitter = QSplitter()
        splitter.setOrientation(Qt.Orientation.Vertical)
        splitter.addWidget(self.results_table)
        splitter.addWidget(self.details)
        splitter.setSizes([440, 260])
        layout.addWidget(splitter, 1)

        self.populate_picker_data()

    def apply_style(self):
        self.setStyleSheet(
            """
            QWidget { background: #f4f6f8; color: #17202a; font-size: 13px; }
            QLabel#title { color: #12344d; font-size: 24px; font-weight: 700; }
            QLabel#subtitle { color: #607080; margin-bottom: 8px; }
            QLineEdit, QSpinBox, QPlainTextEdit, QTableWidget { background: #fff; border: 1px solid #cbd5df; border-radius: 4px; }
            QLineEdit, QSpinBox { padding: 7px; }
            QPushButton { background: #126782; color: white; border: 0; border-radius: 4px; padding: 8px 14px; }
            QPushButton:hover { background: #0d5269; }
            QPushButton:disabled { background: #9aa8b2; }
            QHeaderView::section { background: #e5ebef; padding: 7px; border: 0; font-weight: 600; }
            QPlainTextEdit { font-family: Consolas; font-size: 12px; padding: 8px; }
            """
        )

    def populate_picker_data(self, text=None):
        needle = self.search.text().lower().strip() if text is None else text.lower().strip()
        self.visible_functions = [
            function for function in self.all_functions
            if needle in function.__name__.lower()
        ]
        self.scenario_picker.clear()
        self.scenario_picker.addItems([function.__name__ for function in self.visible_functions])

    def filter_scenarios(self, text):
        self.populate_picker_data(text)
        self.progress.setFormat(f"{len(self.visible_functions)} matching scenario(s)")

    def run_selected(self):
        index = self.scenario_picker.currentIndex()
        if index >= 0:
            self.start_worker(self.visible_functions[index])
            self.progress.setFormat(f"Running: {self.visible_functions[index].__name__}")

    def run_all(self):
        if not self.all_functions or self.running:
            return
        self.clear_results()
        for function in self.visible_functions:
            self.start_worker(function)

    def start_worker(self, scenario_function):
        self.running += 1
        self.set_running(True)
        worker = ScenarioWorker(self.runner, scenario_function)
        worker.signals.result.connect(self.add_result)
        worker.signals.error.connect(self.show_error)
        worker.signals.finished.connect(self.worker_finished)
        self.thread_pool.start(worker)

    def set_running(self, running):
        self.run_selected_button.setEnabled(not running)
        self.run_all_button.setEnabled(not running)
        self.clear_button.setEnabled(not running)

    def add_result(self, result):
        self.results.append(result)
        row = self.results_table.rowCount()
        self.results_table.insertRow(row)
        values = [
            result.get("name", ""), result.get("expected", ""),
            str(result.get("http_status") or ""), result.get("ticket_number") or "",
            result.get("record_status") or "", f"{result.get('duration_ms', 0)} ms",
            "PASS" if result.get("passed") else "FAIL",
        ]
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            if column == 6:
                item.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            self.results_table.setItem(row, column, item)
        self.results_table.item(row, 0).setData(256, result)
        self.results_table.resizeColumnsToContents()
        self.progress.setValue(round(len(self.results) / max(len(self.visible_functions), 1) * 100))

    def show_selected_result(self):
        rows = self.results_table.selectionModel().selectedRows()
        if not rows:
            return
        result = self.results_table.item(rows[0].row(), 0).data(256)
        self.request_view.setPlainText(json.dumps(result.get("payload"), indent=2, default=str))
        self.response_view.setPlainText(json.dumps(result.get("response_json"), indent=2, default=str))
        validation = {
            "passed": result.get("passed"),
            "expected": result.get("expected"),
            "validation_errors": result.get("validation_errors", []),
            "expected_validation_errors": result.get("expected_validation_errors", []),
            "exception": result.get("exception"),
        }
        self.validation_view.setPlainText(json.dumps(validation, indent=2, default=str))

    def worker_finished(self):
        self.running -= 1
        if self.running == 0:
            self.set_running(False)
            passed = sum(1 for result in self.results if result.get("passed"))
            self.progress.setValue(100)
            self.progress.setFormat(f"Complete: {passed}/{len(self.results)} passed")

    def clear_results(self):
        self.results.clear()
        self.results_table.setRowCount(0)
        self.progress.setValue(0)
        self.progress.setFormat("Ready")

    def export_results(self):
        if not self.results:
            QMessageBox.information(self, "Nothing to export", "Run a scenario first.")
            return
        filename, selected_filter = QFileDialog.getSaveFileName(
            self, "Export results", "ticket_results", "JSON (*.json);;CSV (*.csv)"
        )
        if not filename:
            return
        if selected_filter.startswith("CSV") or Path(filename).suffix.lower() == ".csv":
            write_csv(self.results, filename)
        else:
            write_json(self.results, filename)
        self.progress.setFormat(f"Exported {Path(filename).name}")

    def show_error(self, message):
        QMessageBox.critical(self, "Scenario execution error", message)
