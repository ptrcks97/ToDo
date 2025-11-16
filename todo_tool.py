#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ToDo Tool (Deutsch) – PySide6 (Variante C: Gradient NUR im Aufgabenbereich)
- Aufgaben mit Titel, Beschreibung, Priorität, Status, 1–n Subtasks, Finished Date
- JSON-Persistenz (bei jeder Änderung speichern und UI neu laden)
- Filter und Sortierung (Status / Priorität / Titel / Datum)
- Export: Alle im aktuellen Monat auf "Done" gesetzten Tasks (inkl. Subtasks)
- Schöne, moderne Oberfläche; **schwarzer Text**; **pastelliger Verlauf nur im Tree-Bereich**
- Zusatz:
    * Rechts neben jedem Task kompakte Punkt-Indicatoren mit Zählung der Subtask-Status:
        - ToDo
        - Warten (Warte auf Antwort / Warten auf anderen Arbeitstag / Warten auf Mail / Meeting vereinbart)
        - On Hold
        - Done
    * Bugfix: Wenn nur ToDo-Subtasks (oder Mischung aus ToDo/Done) vorhanden sind, ist der Task-Status NICHT mehr fälschlich "On Hold", sondern "ToDo".

Neu:
- 2. Page „Status-Übersicht“ mit zwei Kuchendiagrammen (Tasks / Subtasks nach Status)
- 3. Page „Abschlüsse pro Woche“ mit Balkendiagramm (Anzahl fertiggestellter Tasks pro ISO-Woche)

Voraussetzungen:
    pip install PySide6 PySide6-Addons

Start:
    python todo_tool_gradient_C.py
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any, Tuple, Iterable
from datetime import datetime, date
from pathlib import Path
from collections import defaultdict, OrderedDict

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt

# QtCharts (aus PySide6-Addons)
from PySide6.QtCharts import (
    QChart, QChartView, QPieSeries, QPieSlice,
    QBarSet, QBarSeries, QBarCategoryAxis, QValueAxis
)

APP_NAME = "ToDo Tool"
JSON_FILE = "todos.json"

STATI = [
    "ToDo",
    "Meeting vereinbart",
    "On Hold",
    "Warte auf Antwort",
    "Warten auf anderen Arbeitstag",
    "Warten auf Mail",
    "Done",
]

PRIOS = ["Niedrig", "Mittel", "Hoch", "Kritisch"]

STATUS_PRIORITY_ORDER = [
    "ToDo",
    "Warten auf anderen Arbeitstag",
    "Warten auf Mail",
    "Warte auf Antwort",
    "Meeting vereinbart",
    "On Hold",
    "Done",
]

WAITING_STATUSES = {
    "Warte auf Antwort",
    "Warten auf anderen Arbeitstag",
    "Warten auf Mail",
    "Meeting vereinbart",
}


def iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def group_status(status: str) -> str:
    """Mappt Subtask-Status in 4 Kategorien: todo, waiting, onhold, done."""
    if status == "Done":
        return "done"
    if status == "On Hold":
        return "onhold"
    if status in WAITING_STATUSES:
        return "waiting"
    return "todo"


@dataclass
class Subtask:
    title: str
    description: str = ""
    status: str = "ToDo"
    finished_date: Optional[str] = None
    estimated_hours: float = 0.0
    actual_hours: Optional[float] = None

    def normalize(self):
        if self.status not in STATI:
            self.status = "ToDo"
        if self.status != "Done":
            self.finished_date = None
        try:
            self.estimated_hours = max(0.0, float(self.estimated_hours))
        except (TypeError, ValueError):
            self.estimated_hours = 0.0
        if self.actual_hours is not None:
            try:
                self.actual_hours = max(0.0, float(self.actual_hours))
            except (TypeError, ValueError):
                self.actual_hours = None
        return self

    def set_status(self, new_status: str):
        self.status = new_status
        if new_status == "Done":
            if not self.finished_date:
                self.finished_date = iso_now()
        else:
            self.finished_date = None


@dataclass
class Task:
    title: str
    description: str = ""
    priority: str = "Mittel"
    status: str = "ToDo"
    finished_date: Optional[str] = None
    subtasks: List[Subtask] = field(default_factory=list)

    def normalize(self):
        if self.priority not in PRIOS:
            self.priority = "Mittel"
        if self.status not in STATI:
            self.status = "ToDo"
        for s in self.subtasks:
            s.normalize()
        self.recompute_status_from_subtasks()
        return self

    def recompute_status_from_subtasks(self):
        """Bestimmt den Task-Status anhand der Subtasks.
        Regeln:
          - keine Subtasks: Status bleibt manuell gesetzt; Finished-Date nur bei Done
          - alle Done: Task Done (Finished-Date = max Subtask-Fertig)
          - alle ToDo: Task ToDo
          - Mischung nur aus ToDo/Done: Task ToDo  (BUGFIX)
          - ansonsten: „dominanter“ Nicht-ToDo/Done-Status nach STATUS_PRIORITY_ORDER
        """
        if not self.subtasks:
            if self.status == "Done":
                if not self.finished_date:
                    self.finished_date = iso_now()
            else:
                self.finished_date = None
            return

        sub_statuses = [s.status for s in self.subtasks]

        # Alle done?
        if all(st == "Done" for st in sub_statuses):
            self.status = "Done"
            done_dates = [
                datetime.fromisoformat(s.finished_date)
                for s in self.subtasks
                if s.finished_date
            ]
            if done_dates:
                self.finished_date = max(done_dates).isoformat(timespec="seconds")
            else:
                self.finished_date = iso_now()
            return

        # Alle todo?
        if all(st == "ToDo" for st in sub_statuses):
            self.status = "ToDo"
            self.finished_date = None
            return

        # Mischung nur ToDo/Done => Task bleibt ToDo (BUGFIX)
        uniq = set(sub_statuses)
        if uniq.issubset({"ToDo", "Done"}):
            self.status = "ToDo"
            self.finished_date = None
            return

        # Sonst: dominanter Nicht-(ToDo/Done)-Status
        candidates = [st for st in sub_statuses if st not in ("ToDo", "Done")]
        if candidates:
            candidates.sort(key=lambda s: STATUS_PRIORITY_ORDER.index(s))
            dominant = candidates[-1]
            self.status = dominant
        else:
            self.status = "ToDo"
        self.finished_date = None

    def set_status(self, new_status: str):
        self.status = new_status
        if new_status == "Done":
            if not self.finished_date:
                self.finished_date = iso_now()
        else:
            self.finished_date = None


def load_tasks(path: Path) -> List[Task]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        tasks: List[Task] = []
        for t in data:
            subtasks = [Subtask(**s) for s in t.get("subtasks", [])]
            task = Task(
                title=t.get("title", ""),
                description=t.get("description", ""),
                priority=t.get("priority", "Mittel"),
                status=t.get("status", "ToDo"),
                finished_date=t.get("finished_date"),
                subtasks=subtasks,
            ).normalize()
            tasks.append(task)
        return tasks
    except Exception as e:
        QtWidgets.QMessageBox.critical(None, "Fehler beim Laden", f"JSON konnte nicht gelesen werden:\n{e}")
        return []


def save_tasks(path: Path, tasks: List[Task]) -> None:
    try:
        serializable = []
        for t in tasks:
            t.normalize()
            serializable.append({
                "title": t.title,
                "description": t.description,
                "priority": t.priority,
                "status": t.status,
                "finished_date": t.finished_date,
                "subtasks": [asdict(s) for s in t.subtasks],
            })
        path.write_text(json.dumps(serializable, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        QtWidgets.QMessageBox.critical(None, "Fehler beim Speichern", f"JSON konnte nicht gespeichert werden:\n{e}")


class TaskDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, task: Optional[Task]=None):
        super().__init__(parent)
        self.setWindowTitle("Aufgabe bearbeiten" if task else "Neue Aufgabe")
        self.setMinimumWidth(560)

        self.title_edit = QtWidgets.QLineEdit()
        self.desc_edit = QtWidgets.QPlainTextEdit()
        self.prio_combo = QtWidgets.QComboBox()
        self.prio_combo.addItems(PRIOS)

        self.status_combo = QtWidgets.QComboBox()
        self.status_combo.addItems(STATI)

        form = QtWidgets.QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        form.addRow("Titel:", self.title_edit)
        form.addRow("Beschreibung:", self.desc_edit)
        form.addRow("Priorität:", self.prio_combo)
        form.addRow("Status:", self.status_combo)

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.addLayout(form)
        layout.addWidget(btns)

        self._task = task
        if task:
            self.title_edit.setText(task.title)
            self.desc_edit.setPlainText(task.description)
            self.prio_combo.setCurrentIndex(max(PRIOS.index(task.priority), 0))
            self.status_combo.setCurrentIndex(max(STATI.index(task.status), 0))

    def get_task_data(self) -> Task:
        title = self.title_edit.text().strip()
        desc = self.desc_edit.toPlainText().strip()
        prio = self.prio_combo.currentText()
        status = self.status_combo.currentText()
        if not title:
            raise ValueError("Titel darf nicht leer sein.")
        if self._task:
            t = self._task
            t.title = title
            t.description = desc
            t.priority = prio
            if not t.subtasks:
                t.set_status(status)
        else:
            t = Task(title=title, description=desc, priority=prio, status=status)
        return t.normalize()


class SubtaskDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, subtask: Optional[Subtask]=None):
        super().__init__(parent)
        self.setWindowTitle("Subtask bearbeiten" if subtask else "Neuer Subtask")
        self.setMinimumWidth(520)
        self._suspend_status_prompt = False

        self.title_edit = QtWidgets.QLineEdit()
        self.desc_edit = QtWidgets.QPlainTextEdit()
        self.status_combo = QtWidgets.QComboBox()
        self.status_combo.addItems(STATI)
        self.status_combo.currentTextChanged.connect(self._on_status_changed)

        self.estimate_spin = QtWidgets.QDoubleSpinBox()
        self.estimate_spin.setRange(0.0, 1000.0)
        self.estimate_spin.setDecimals(2)
        self.estimate_spin.setSingleStep(0.25)
        self.estimate_spin.setSuffix(" h")

        self.actual_time_spin = QtWidgets.QDoubleSpinBox()
        self.actual_time_spin.setRange(0.0, 1000.0)
        self.actual_time_spin.setDecimals(2)
        self.actual_time_spin.setSingleStep(0.25)
        self.actual_time_spin.setSuffix(" h")
        self.actual_time_spin.setEnabled(False)

        form = QtWidgets.QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        form.addRow("Titel:", self.title_edit)
        form.addRow("Beschreibung:", self.desc_edit)
        form.addRow("Status:", self.status_combo)
        form.addRow("Zeitschätzung (Std.):", self.estimate_spin)
        form.addRow("Ist-Zeit (Std.):", self.actual_time_spin)

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.addLayout(form)
        layout.addWidget(btns)

        self._subtask = subtask
        self._last_status = subtask.status if subtask else "ToDo"
        self._suspend_status_prompt = True
        if subtask:
            self.title_edit.setText(subtask.title)
            self.desc_edit.setPlainText(subtask.description)
            self.status_combo.setCurrentIndex(max(STATI.index(subtask.status), 0))
            self.estimate_spin.setValue(float(subtask.estimated_hours or 0.0))
            if subtask.actual_hours:
                self.actual_time_spin.setValue(float(subtask.actual_hours))
        else:
            self.status_combo.setCurrentIndex(max(STATI.index("ToDo"), 0))
        self._suspend_status_prompt = False
        self._on_status_changed(self.status_combo.currentText())

    def get_subtask_data(self) -> Subtask:
        title = self.title_edit.text().strip()
        desc = self.desc_edit.toPlainText().strip()
        status = self.status_combo.currentText()
        if not title:
            raise ValueError("Titel darf nicht leer sein.")
        if self._subtask:
            s = self._subtask
            s.title = title
            s.description = desc
            s.set_status(status)
        else:
            s = Subtask(title=title, description=desc, status=status)
        s.estimated_hours = self.estimate_spin.value()
        s.actual_hours = self.actual_time_spin.value() if status == "Done" else None
        return s.normalize()

    def _on_status_changed(self, status: str):
        if self._suspend_status_prompt:
            self._update_actual_field_state(status)
            self._last_status = status
            return

        self._update_actual_field_state(status)
        if status == "Done" and self.actual_time_spin.value() <= 0.0:
            if not self._prompt_actual_time():
                self._suspend_status_prompt = True
                self.status_combo.setCurrentText(self._last_status)
                self._suspend_status_prompt = False
                self._update_actual_field_state(self._last_status)
                return
        self._last_status = status

    def _update_actual_field_state(self, status: str):
        self.actual_time_spin.setEnabled(status == "Done")

    def _prompt_actual_time(self) -> bool:
        suggested = self.actual_time_spin.value() or self.estimate_spin.value()
        value, ok = QtWidgets.QInputDialog.getDouble(
            self,
            "Ist-Zeit erfassen",
            "Bitte gib die tatsächlich benötigte Zeit in Stunden ein:",
            suggested,
            0.0,
            1000.0,
            2,
        )
        if ok:
            self.actual_time_spin.setValue(value)
            return True
        return False


# ---------- Charts-Seiten ----------

class StatusChartsPage(QtWidgets.QWidget):
    """Page mit zwei Kuchendiagrammen: Tasks nach Status, Subtasks nach Status"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.task_chart = self._build_pie_chart("Tasks nach Status")
        self.subtask_chart = self._build_pie_chart("Subtasks nach Status")

        self.task_view = QChartView(self.task_chart)
        self.subtask_view = QChartView(self.subtask_chart)
        for v in (self.task_view, self.subtask_view):
            v.setRenderHint(QtGui.QPainter.Antialiasing, True)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)
        layout.addWidget(self.task_view, 1)
        layout.addWidget(self.subtask_view, 1)

    def _build_pie_chart(self, title: str) -> QChart:
        chart = QChart()
        chart.setTitle(title)
        chart.setBackgroundBrush(QtGui.QBrush(QtGui.QColor("#FFFFFF")))
        chart.setTitleBrush(QtGui.QBrush(QtGui.QColor("#000000")))
        chart.legend().setVisible(True)
        chart.legend().setLabelBrush(QtGui.QBrush(QtGui.QColor("#000000")))
        return chart

    def _apply_slice_style(self, series: QPieSeries):
        # Labels sichtbar + schwarz
        series.setLabelsVisible(True)
        for i in range(series.count()):
            sl: QPieSlice = series.slices()[i]
            sl.setLabelBrush(QtGui.QBrush(QtGui.QColor("#000000")))
            sl.setPen(QtGui.QPen(QtGui.QColor(0,0,0,40)))
            # dezente Pastellfarben pro Status (konstant)
            status = sl.label().split(" (")[0]
            color_map = {
                "ToDo": "#C3D6FD",
                "Warten auf anderen Arbeitstag": "#FDE68A",
                "Warten auf Mail": "#F9E79F",
                "Warte auf Antwort": "#FCD34D",
                "Meeting vereinbart": "#FDE2E2",
                "On Hold": "#F86B6B",
                "Done": "#BDFFDD",
            }
            c = QtGui.QColor(color_map.get(status, "#E5E7EB"))
            sl.setBrush(QtGui.QBrush(c))

    def update_counts(self, task_counts: Dict[str, int], sub_counts: Dict[str, int]):
        # Tasks
        t_series = QPieSeries()
        for st in STATI:
            val = int(task_counts.get(st, 0))
            if val > 0:
                t_series.append(f"{st} ({val})", val)
        self._apply_slice_style(t_series)

        self.task_chart.removeAllSeries()
        self.task_chart.addSeries(t_series)
        self.task_chart.legend().setLabelBrush(QtGui.QBrush(QtGui.QColor("#000000")))

        # Subtasks
        s_series = QPieSeries()
        for st in STATI:
            val = int(sub_counts.get(st, 0))
            if val > 0:
                s_series.append(f"{st} ({val})", val)
        self._apply_slice_style(s_series)

        self.subtask_chart.removeAllSeries()
        self.subtask_chart.addSeries(s_series)
        self.subtask_chart.legend().setLabelBrush(QtGui.QBrush(QtGui.QColor("#000000")))


class WeeklyDonePage(QtWidgets.QWidget):
    """Page mit Balkendiagramm: Anzahl erledigter Tasks pro ISO-Woche"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.chart = QChart()
        self.chart.setTitle("Abgeschlossene Tasks pro ISO-Woche")
        self.chart.setBackgroundBrush(QtGui.QBrush(QtGui.QColor("#FFFFFF")))
        self.chart.setTitleBrush(QtGui.QBrush(QtGui.QColor("#000000")))
        self.chart.legend().setVisible(False)

        self.view = QChartView(self.chart)
        self.view.setRenderHint(QtGui.QPainter.Antialiasing, True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        layout.addWidget(self.view, 1)

    def update_weeks(self, week_counts: "OrderedDict[str, int]"):
        # week_counts: Ordered nach Datum (z.B. "2025-W43": 7)
        categories = list(week_counts.keys())
        values = list(week_counts.values())

        bar_set = QBarSet("Done")
        bar_set.append(values)
        # dezente Füllung + Kontur
        bar_set.setBrush(QtGui.QBrush(QtGui.QColor("#BDFFDD")))
        bar_set.setPen(QtGui.QPen(QtGui.QColor(0,0,0,60)))

        series = QBarSeries()
        series.append(bar_set)

        self.chart.removeAllSeries()
        self.chart.addSeries(series)

        axisX = QBarCategoryAxis()
        axisX.append(categories)
        axisX.setLabelsBrush(QtGui.QBrush(QtGui.QColor("#000000")))
        axisX.setTitleText("Woche")
        axisX.setTitleBrush(QtGui.QBrush(QtGui.QColor("#000000")))

        axisY = QValueAxis()
        axisY.setLabelFormat("%d")
        axisY.setMin(0)
        axisY.setMax(max(values) if values else 1)
        axisY.setLabelsBrush(QtGui.QBrush(QtGui.QColor("#000000")))
        axisY.setTitleText("Anzahl Tasks (Done)")
        axisY.setTitleBrush(QtGui.QBrush(QtGui.QColor("#000000")))

        self.chart.createDefaultAxes()  # sorgt für Grundachsen
        self.chart.setAxisX(axisX, series)
        self.chart.setAxisY(axisY, series)


class TimeComparisonPage(QtWidgets.QWidget):
    """Page mit Balkendiagramm (geschätzte vs. tatsächliche Zeit in Stunden)"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.chart = QChart()
        self.chart.setTitle("Zeitvergleich (Subtasks)")
        self.chart.setBackgroundBrush(QtGui.QBrush(QtGui.QColor("#FFFFFF")))
        self.chart.setTitleBrush(QtGui.QBrush(QtGui.QColor("#000000")))
        self.chart.legend().setVisible(True)
        self.chart.legend().setLabelBrush(QtGui.QBrush(QtGui.QColor("#000000")))

        self.view = QChartView(self.chart)
        self.view.setRenderHint(QtGui.QPainter.Antialiasing, True)

        self.info_label = QtWidgets.QLabel()
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: #000000; font-weight: 600;")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        layout.addWidget(self.view, 1)
        layout.addWidget(self.info_label, 0)

    def update_values(self, estimated_hours: float, actual_hours: float):
        categories = ["Summe"]

        est_set = QBarSet("Geschätzt")
        est_set.append([estimated_hours])
        est_set.setBrush(QtGui.QBrush(QtGui.QColor("#C3D6FD")))
        est_set.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 40)))

        act_set = QBarSet("Ist")
        act_set.append([actual_hours])
        act_set.setBrush(QtGui.QBrush(QtGui.QColor("#BDFFDD")))
        act_set.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 40)))

        series = QBarSeries()
        series.append(est_set)
        series.append(act_set)

        self.chart.removeAllSeries()
        self.chart.addSeries(series)

        axisX = QBarCategoryAxis()
        axisX.append(categories)
        axisX.setLabelsBrush(QtGui.QBrush(QtGui.QColor("#000000")))

        axisY = QValueAxis()
        axisY.setLabelFormat("%.1f")
        axisY.setMin(0.0)
        axisY.setMax(max(estimated_hours, actual_hours, 1.0))
        axisY.setLabelsBrush(QtGui.QBrush(QtGui.QColor("#000000")))
        axisY.setTitleText("Stunden")
        axisY.setTitleBrush(QtGui.QBrush(QtGui.QColor("#000000")))

        self.chart.createDefaultAxes()
        self.chart.setAxisX(axisX, series)
        self.chart.setAxisY(axisY, series)

        difference = actual_hours - estimated_hours
        if estimated_hours > 0:
            ratio = (actual_hours / estimated_hours) * 100.0
            ratio_text = f"{ratio:.1f}% der geschätzten Zeit"
        else:
            ratio_text = "Keine Schätzung vorhanden"
        self.info_label.setText(
            f"Geschätzt: {estimated_hours:.2f} h | Tatsächlich: {actual_hours:.2f} h | Abweichung: {difference:+.2f} h ({ratio_text})"
        )


# ---------- Main Window ----------

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1180, 780)

        # Tabs
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabPosition(QtWidgets.QTabWidget.North)

        # Seite 1: Tree
        self.page_tree = QtWidgets.QWidget()
        self.tree = QtWidgets.QTreeWidget()
        self.tree.viewport().setAttribute(Qt.WA_StyledBackground, True)
        self.tree.setAlternatingRowColors(False)
        self.tree.setColumnCount(6)
        self.tree.setHeaderLabels(["Titel", "Beschreibung", "Priorität", "Status", "Fertig am", "Typ"])
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tree.setUniformRowHeights(True)
        self.tree.setAnimated(True)
        self.tree.setIndentation(24)
        self.tree.setItemDelegate(RowDelegate(self.tree))

        tree_layout = QtWidgets.QVBoxLayout(self.page_tree)
        tree_layout.setContentsMargins(0, 0, 0, 0)
        tree_layout.addWidget(self.tree)

        self.tabs.addTab(self.page_tree, "Aufgaben")

        # Seite 2: Charts (Status)
        self.status_page = StatusChartsPage()
        self.tabs.addTab(self.status_page, "Status-Übersicht")

        # Seite 3: Weekly Done
        self.weekly_page = WeeklyDonePage()
        self.tabs.addTab(self.weekly_page, "Abschlüsse pro Woche")

        # Seite 4: Zeitvergleich
        self.time_page = TimeComparisonPage()
        self.tabs.addTab(self.time_page, "Zeitvergleich")

        self.setCentralWidget(self.tabs)

        self._create_actions()
        self._create_toolbar()
        self._create_filter_panel()

        self.statusBar().showMessage("Bereit")

        self._apply_styles()

        self.path = Path(JSON_FILE)
        self.tasks: List[Task] = []
        self.load_and_refresh()

        self.tree.itemDoubleClicked.connect(self.edit_selected_item)

    # ----- UI Bausätze -----

    def _create_actions(self):
        self.act_add_task = QtGui.QAction("Aufgabe", self)
        self.act_add_task.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_FileDialogNewFolder))
        self.act_add_task.triggered.connect(self.add_task)

        self.act_edit = QtGui.QAction("Bearbeiten", self)
        self.act_edit.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_FileDialogDetailedView))
        self.act_edit.triggered.connect(self.edit_selected_item)

        self.act_delete = QtGui.QAction("Löschen", self)
        self.act_delete.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_TrashIcon))
        self.act_delete.triggered.connect(self.delete_selected_item)

        self.act_add_sub = QtGui.QAction("Subtask", self)
        self.act_add_sub.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_FileDialogListView))
        self.act_add_sub.triggered.connect(self.add_subtask_to_selected)

        self.act_mark_done = QtGui.QAction("Als Done setzen", self)
        self.act_mark_done.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DialogApplyButton))
        self.act_mark_done.triggered.connect(self.mark_selected_done)

        self.act_export = QtGui.QAction("Export", self)
        self.act_export.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DialogSaveButton))
        self.act_export.triggered.connect(self.export_month_done)

        self.act_reload = QtGui.QAction("Neu laden", self)
        self.act_reload.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_BrowserReload))
        self.act_reload.triggered.connect(self.load_and_refresh)

    def _create_toolbar(self):
        tb = self.addToolBar("Aktionen")
        tb.setMovable(False)
        tb.addAction(self.act_add_task)
        tb.addAction(self.act_add_sub)
        tb.addAction(self.act_edit)
        tb.addAction(self.act_delete)
        tb.addSeparator()
        tb.addAction(self.act_mark_done)
        tb.addSeparator()
        tb.addAction(self.act_export)
        tb.addAction(self.act_reload)

    def _create_filter_panel(self):
        panel = QtWidgets.QWidget()
        hl = QtWidgets.QHBoxLayout(panel)
        hl.setContentsMargins(12, 8, 12, 8)
        hl.setSpacing(12)

        hl.addWidget(QtWidgets.QLabel("Filter Status:"))
        self.filter_status = QtWidgets.QComboBox()
        self.filter_status.addItem("Alle")
        self.filter_status.addItems(STATI)
        self.filter_status.currentIndexChanged.connect(self.refresh_all_views)
        hl.addWidget(self.filter_status)

        hl.addWidget(QtWidgets.QLabel("Filter Prio:"))
        self.filter_prio = QtWidgets.QComboBox()
        self.filter_prio.addItem("Alle")
        self.filter_prio.addItems(PRIOS)
        self.filter_prio.currentIndexChanged.connect(self.refresh_all_views)
        hl.addWidget(self.filter_prio)

        hl.addWidget(QtWidgets.QLabel("Sortieren nach:"))
        self.sort_by = QtWidgets.QComboBox()
        self.sort_by.addItems(["Priorität", "Status", "Titel", "Fertig am"])
        self.sort_by.currentIndexChanged.connect(self.refresh_tree_view)
        hl.addWidget(self.sort_by)

        self.sort_dir = QtWidgets.QComboBox()
        self.sort_dir.addItems(["Aufsteigend", "Absteigend"])
        self.sort_dir.currentIndexChanged.connect(self.refresh_tree_view)
        hl.addWidget(self.sort_dir)

        hl.addWidget(QtWidgets.QLabel("Suche:"))
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Titel/Beschreibung...")
        self.search_edit.textChanged.connect(self.refresh_tree_view)
        hl.addWidget(self.search_edit, 1)

        dock = QtWidgets.QDockWidget("Filter & Sortierung", self)
        dock.setWidget(panel)
        dock.setFeatures(QtWidgets.QDockWidget.NoDockWidgetFeatures)
        self.addDockWidget(Qt.TopDockWidgetArea, dock)

    def _apply_styles(self):
        self.setStyleSheet("""
            /* --- Grundfarben hell, Texte schwarz --- */
            * { font-size: 14px; }
            QMainWindow {
                background: #FFFFFF;
                color: #000000;
            }
            QDockWidget {
                background: #FFFFFF;
                color: #000000;
                border: 1px solid #E5E7EB;
                border-radius: 12px;
            }
            QLabel {
                color: #000000;
                font-weight: 600;
            }
            QLineEdit, QPlainTextEdit, QComboBox {
                background: #FFFFFF;
                color: #000000;
                border: 1px solid #E5E7EB;
                border-radius: 10px;
                padding: 8px 10px;
                selection-background-color: #D0E7FF;
                selection-color: #000000;
            }
            QPlainTextEdit { padding: 10px; }
            QToolBar {
                background: #FFFFFF;
                spacing: 8px;
                padding: 8px;
                border-bottom: 1px solid #E5E7EB;
            }
            QToolButton {
                color: #000000;
                background: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 12px;
                padding: 8px 12px;
            }
            QToolButton:hover { background: #F7F9FB; }
            QToolButton:pressed { background: #EEF3F8; }

            QHeaderView::section {
                background: #FFFFFF;
                color: #000000;
                padding: 10px 8px;
                border: none;
                border-bottom: 1px solid #E5E7EB;
                font-weight: 600;
            }

            /* Pastell-Gradient NUR im Tree-Widget */
            QTreeWidget { background: transparent; border: none; color: #000000; }

            QTreeWidget::viewport {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0    #f8a1c4,
                    stop:0.25 #ffd7a8,
                    stop:0.5  #fff2b3,
                    stop:0.75 #c8f3e1,
                    stop:1    #cde7ff
                );
            }

            /* Items transparent lassen – wir malen Tasks selbst weiß im Delegate */
            QTreeView::item { background: transparent; color: #000000; }
            QTreeView::item:hover    { background: rgba(0,0,0,0.03); }
            QTreeView::item:selected { background: rgba(30,144,255,0.22); color:#000000; }

            QDialog {
                background: #FFFFFF;
                color: #000000;
            }
            QDialog QPushButton {
                background: #FFFFFF;
                color: #000000;
                border: 1px solid #E5E7EB;
                border-radius: 10px;
                padding: 8px 14px;
            }
            QDialog QPushButton:hover { background: #F7F9FB; }

            QStatusBar { color: #000000; }
        """)

    # ----- Refresh-Flow -----

    def load_and_refresh(self):
        self.tasks = load_tasks(self.path)
        self.refresh_all_views()

    def persist_and_reload(self):
        save_tasks(self.path, self.tasks)
        self.load_and_refresh()

    def refresh_all_views(self):
        self.refresh_tree_view()
        self.refresh_status_charts()
        self.refresh_weekly_done()
        self.refresh_time_comparison()

    # ----- Helpers für Charts -----

    def _status_counts_tasks(self) -> Dict[str, int]:
        counts = {st: 0 for st in STATI}
        for t in self.tasks:
            counts[t.status] = counts.get(t.status, 0) + 1
        return counts

    def _status_counts_subtasks(self) -> Dict[str, int]:
        counts = {st: 0 for st in STATI}
        for t in self.tasks:
            for s in t.subtasks:
                counts[s.status] = counts.get(s.status, 0) + 1
        return counts

    def _week_key(self, dt: date) -> Tuple[int, int]:
        # ISO-Kalender: (ISO-Jahr, ISO-Woche)
        iso_year, iso_week, _ = dt.isocalendar()
        return (iso_year, iso_week)

    def _format_week_label(self, y: int, w: int) -> str:
        return f"{y}-W{w:02d}"

    def _weekly_done_counts(self) -> "OrderedDict[str, int]":
        tmp: Dict[Tuple[int,int], int] = defaultdict(int)
        for t in self.tasks:
            if t.status == "Done" and t.finished_date:
                try:
                    d = datetime.fromisoformat(t.finished_date).date()
                    key = self._week_key(d)
                    tmp[key] += 1
                except Exception:
                    pass
        # sortieren nach (jahr, woche)
        ordered = OrderedDict()
        for (y, w) in sorted(tmp.keys()):
            ordered[self._format_week_label(y, w)] = tmp[(y, w)]
        return ordered

    def refresh_status_charts(self):
        task_counts = self._status_counts_tasks()
        sub_counts = self._status_counts_subtasks()
        self.status_page.update_counts(task_counts, sub_counts)

    def refresh_weekly_done(self):
        weeks = self._weekly_done_counts()
        self.weekly_page.update_weeks(weeks)

    def _time_totals(self) -> Tuple[float, float]:
        est = 0.0
        actual = 0.0
        for t in self.tasks:
            for s in t.subtasks:
                if s.status == "Done":
                    est += max(0.0, float(s.estimated_hours or 0.0))
                    actual += max(0.0, float(s.actual_hours or 0.0))
        return (est, actual)

    def refresh_time_comparison(self):
        est, actual = self._time_totals()
        self.time_page.update_values(est, actual)

    # ----- Tree/CRUD -----

    def _subtask_counts(self, t: Task) -> Dict[str, int]:
        counts = {"todo": 0, "waiting": 0, "onhold": 0, "done": 0}
        for s in t.subtasks:
            counts[group_status(s.status)] += 1
        return counts

    def _format_subtask_time_tooltip(self, subtask: Subtask) -> str:
        est = max(0.0, float(subtask.estimated_hours or 0.0))
        actual = subtask.actual_hours
        actual_txt = f"{actual:.2f} h" if actual is not None else "–"
        return f"Zeitschätzung: {est:.2f} h | Tatsächlich: {actual_txt}"

    def _ensure_actual_time(self, subtask: Subtask) -> bool:
        if subtask.actual_hours is not None and subtask.actual_hours > 0:
            return True
        suggested = max(0.0, float(subtask.estimated_hours or 0.0))
        value, ok = QtWidgets.QInputDialog.getDouble(
            self,
            "Ist-Zeit erfassen",
            f"Tatsächliche Zeit für „{subtask.title}“ (in Stunden):",
            suggested,
            0.0,
            1000.0,
            2,
        )
        if ok:
            subtask.actual_hours = value
            return True
        return False

    def refresh_tree_view(self):
        self.tree.clear()

        f_status = self.filter_status.currentText()
        f_prio = self.filter_prio.currentText()
        query = self.search_edit.text().lower().strip()

        def task_visible(t: Task) -> bool:
            if f_status != "Alle" and t.status != f_status:
                return False
            if f_prio != "Alle" and t.priority != f_prio:
                return False
            if query and (query not in t.title.lower() and query not in t.description.lower()):
                return False
            return True

        key_name = self.sort_by.currentText()
        reverse = (self.sort_dir.currentText() == "Absteigend")

        def sort_key(t: Task):
            if key_name == "Priorität":
                return PRIOS.index(t.priority)
            if key_name == "Status":
                return STATUS_PRIORITY_ORDER.index(t.status)
            if key_name == "Titel":
                return t.title.lower()
            if key_name == "Fertig am":
                return datetime.fromisoformat(t.finished_date) if t.finished_date else datetime.min
            return t.title.lower()

        tasks_sorted = sorted(self.tasks, key=sort_key, reverse=reverse)

        for t in tasks_sorted:
            if not task_visible(t):
                continue
            top = QtWidgets.QTreeWidgetItem([
                t.title,
                t.description,
                t.priority,
                t.status,
                t.finished_date or "",
                "Task",
            ])
            top.setForeground(0, QtGui.QBrush(QtGui.QColor("#000000")))
            top.setData(0, Qt.UserRole, ("task", id(t)))

            counts = self._subtask_counts(t)
            top.setData(0, Qt.UserRole + 1, counts)
            tt = (f"Subtasks – ToDo: {counts['todo']} | Warten: {counts['waiting']} | "
                  f"On Hold: {counts['onhold']} | Done: {counts['done']}")
            top.setToolTip(0, tt)

            for s in t.subtasks:
                child = QtWidgets.QTreeWidgetItem([
                    s.title, s.description, "", s.status, s.finished_date or "", "Subtask"
                ])
                child.setData(0, Qt.UserRole, ("subtask", id(t), id(s)))
                tip = self._format_subtask_time_tooltip(s)
                child.setToolTip(0, tip)
                child.setToolTip(1, tip)
                top.addChild(child)

            self.tree.addTopLevelItem(top)
            self.tree.expandItem(top)

        self.tree.resizeColumnToContents(0)
        self.tree.resizeColumnToContents(2)
        self.tree.resizeColumnToContents(3)
        self.tree.setColumnWidth(1, 460)

        self.statusBar().showMessage(f"{self.tree.topLevelItemCount()} Aufgaben angezeigt")

    def current_selection(self):
        item = self.tree.currentItem()
        if not item:
            return None
        data = item.data(0, Qt.UserRole)
        return data

    def find_task_by_id(self, obj_id: int) -> Optional[Task]:
        for t in self.tasks:
            if id(t) == obj_id:
                return t
        return None

    def find_subtask_by_id(self, task: Task, sub_id: int) -> Optional[Subtask]:
        for s in task.subtasks:
            if id(s) == sub_id:
                return s
        return None

    def add_task(self):
        dlg = TaskDialog(self)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            try:
                new_task = dlg.get_task_data()
                self.tasks.append(new_task)
                self.persist_and_reload()
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Eingabe unvollständig", str(e))

    def edit_selected_item(self):
        sel = self.current_selection()
        if not sel:
            return
        if sel[0] == "task":
            task = self.find_task_by_id(sel[1])
            if not task:
                return
            dlg = TaskDialog(self, task)
            if dlg.exec() == QtWidgets.QDialog.Accepted:
                try:
                    dlg.get_task_data()
                    task.normalize()
                    self.persist_and_reload()
                except Exception as e:
                    QtWidgets.QMessageBox.warning(self, "Fehler", str(e))
        elif sel[0] == "subtask":
            task = self.find_task_by_id(sel[1])
            sub = self.find_subtask_by_id(task, sel[2]) if task else None
            if not task or not sub:
                return
            dlg = SubtaskDialog(self, sub)
            if dlg.exec() == QtWidgets.QDialog.Accepted:
                try:
                    dlg.get_subtask_data()
                    task.recompute_status_from_subtasks()
                    self.persist_and_reload()
                except Exception as e:
                    QtWidgets.QMessageBox.warning(self, "Fehler", str(e))

    def delete_selected_item(self):
        sel = self.current_selection()
        if not sel:
            return
        if sel[0] == "task":
            task = self.find_task_by_id(sel[1])
            if not task:
                return
            if QtWidgets.QMessageBox.question(self, "Löschen?", f"Aufgabe „{task.title}“ löschen?") == QtWidgets.QMessageBox.Yes:
                self.tasks.remove(task)
                self.persist_and_reload()
        elif sel[0] == "subtask":
            task = self.find_task_by_id(sel[1])
            sub = self.find_subtask_by_id(task, sel[2]) if task else None
            if not task or not sub:
                return
            if QtWidgets.QMessageBox.question(self, "Löschen?", f"Subtask „{sub.title}“ löschen?") == QtWidgets.QMessageBox.Yes:
                task.subtasks.remove(sub)
                task.recompute_status_from_subtasks()
                self.persist_and_reload()

    def add_subtask_to_selected(self):
        sel = self.current_selection()
        if not sel or sel[0] not in ("task", "subtask"):
            QtWidgets.QMessageBox.information(self, "Hinweis", "Bitte zuerst eine Aufgabe oder einen Subtask (unter einer Aufgabe) auswählen.")
            return
        task = self.find_task_by_id(sel[1])
        if not task:
            return
        dlg = SubtaskDialog(self)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            try:
                sub = dlg.get_subtask_data()
                task.subtasks.append(sub)
                task.recompute_status_from_subtasks()
                self.persist_and_reload()
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Fehler", str(e))

    def mark_selected_done(self):
        sel = self.current_selection()
        if not sel:
            return
        if sel[0] == "task":
            task = self.find_task_by_id(sel[1])
            if not task:
                return
            if task.subtasks:
                for s in task.subtasks:
                    previous_status = s.status
                    s.set_status("Done")
                    if not self._ensure_actual_time(s):
                        s.set_status(previous_status)
                        task.recompute_status_from_subtasks()
                        return
                task.recompute_status_from_subtasks()
            else:
                task.set_status("Done")
            self.persist_and_reload()
        elif sel[0] == "subtask":
            task = self.find_task_by_id(sel[1])
            sub = self.find_subtask_by_id(task, sel[2]) if task else None
            if not task or not sub:
                return
            previous_status = sub.status
            sub.set_status("Done")
            if not self._ensure_actual_time(sub):
                sub.set_status(previous_status)
                return
            task.recompute_status_from_subtasks()
            self.persist_and_reload()

    def export_month_done(self):
        today = datetime.now()
        y, m = today.year, today.month

        export: List[Dict[str, Any]] = []
        for t in self.tasks:
            task_done_this_month = False
            if t.finished_date:
                try:
                    dt = datetime.fromisoformat(t.finished_date)
                    task_done_this_month = (dt.year == y and dt.month == m and t.status == "Done")
                except Exception:
                    pass

            subtasks_done = []
            for s in t.subtasks:
                if s.finished_date and s.status == "Done":
                    try:
                        sd = datetime.fromisoformat(s.finished_date)
                        if sd.year == y and sd.month == m:
                            subtasks_done.append({
                                "title": s.title,
                                "description": s.description,
                                "finished_date": s.finished_date,
                            })
                    except Exception:
                        pass

            if task_done_this_month or subtasks_done:
                export.append({
                    "title": t.title,
                    "description": t.description,
                    "priority": t.priority,
                    "task_finished_date": t.finished_date if task_done_this_month else None,
                    "subtasks_done": subtasks_done,
                })

        if not export:
            QtWidgets.QMessageBox.information(self, "Export", "Keine erledigten Aufgaben in diesem Monat gefunden.")
            return

        html_parts = ["""
        <!doctype html>
        <html lang="de">
        <head>
          <meta charset="utf-8">
          <title>Erledigt-Report</title>
          <style>
            body { font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; background:#ffffff; color:#000; padding:32px; }
            h1 { color:#111; }
            .task { background:#ffffff; border:1px solid #e5e7eb; border-radius:16px; padding:16px 20px; margin:16px 0; }
            .meta { color:#374151; font-size:0.95em; }
            .subtask { background:#fafafa; border:1px dashed #d1d5db; border-radius:12px; padding:12px; margin:10px 0; }
            .date { color:#111; }
            .prio { font-weight:700; }
            .muted { color:#4b5563; }
          </style>
        </head>
        <body>
        """]
        html_parts.append(f"<h1>Erledigt im {today.strftime('%B %Y')}</h1>")

        for e in export:
            html_parts.append('<div class="task">')
            html_parts.append(f"<h2>{e['title']}</h2>")
            html_parts.append(f"<p class='muted'>{e['description'] or ''}</p>")
            html_parts.append(f"<p class='meta'><span class='prio'>Priorität:</span> {e['priority']}</p>")
            if e["task_finished_date"]:
                html_parts.append(f"<p class='date'>Task fertig am: {e['task_finished_date']}</p>")
            if e["subtasks_done"]:
                html_parts.append("<div>")
                html_parts.append("<h3>Erledigte Subtasks:</h3>")
                for s in e["subtasks_done"]:
                    html_parts.append('<div class="subtask">')
                    html_parts.append(f"<strong>{s['title']}</strong>")
                    if s["description"]:
                        html_parts.append(f"<div class='muted'>{s['description']}</div>")
                    html_parts.append(f"<div class='date'>fertig am: {s['finished_date']}</div>")
                    html_parts.append("</div>")
                html_parts.append("</div>")
            html_parts.append("</div>")

        html_parts.append("</body></html>")
        html = "\n".join(html_parts)

        export_name = f"todo_export_{y:04d}_{m:02d}.html"
        out_path = Path(export_name)
        out_path.write_text(html, encoding="utf-8")

        QtWidgets.QMessageBox.information(self, "Export", f"Export gespeichert: {out_path.resolve()}")

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        save_tasks(self.path, self.tasks)
        super().closeEvent(event)


def ensure_json_exists(path: Path):
    if not path.exists():
        sample = [
            {
                "title": "Beispielprojekt",
                "description": "Erste Aufgabe als Beispiel",
                "priority": "Mittel",
                "status": "ToDo",
                "finished_date": None,
                "subtasks": [
                    {
                        "title": "Recherche",
                        "description": "Infos sammeln",
                        "status": "ToDo",
                        "finished_date": None,
                        "estimated_hours": 2.0,
                        "actual_hours": None,
                    },
                    {
                        "title": "Kontakt aufnehmen",
                        "description": "E-Mail schreiben",
                        "status": "Warte auf Antwort",
                        "finished_date": None,
                        "estimated_hours": 1.0,
                        "actual_hours": None,
                    },
                ]
            }
        ]
        path.write_text(json.dumps(sample, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    import sys
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    QtWidgets.QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    ensure_json_exists(Path(JSON_FILE))

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


class RowDelegate(QtWidgets.QStyledItemDelegate):
    """Malt für Top-Level-Tasks eine „Karte“ + rechts die Subtask-Status-Indikatoren (Punkte mit Zahl)."""
    # Farben für die vier Kategorien (pastellig, auf Weiß gut sichtbar – Text bleibt schwarz)
    COLOR_TODO   = QtGui.QColor("#C3D6FD")   # graublau
    COLOR_WAIT   = QtGui.QColor("#F59E0B")   # amber
    COLOR_ONHOLD = QtGui.QColor("#F86B6B")   # violett/rot
    COLOR_DONE   = QtGui.QColor("#BDFFDD")   # grün

    def _draw_indicator(self, painter: QtGui.QPainter, center: QtCore.QPointF, radius: float, color: QtGui.QColor, text: str):
        painter.save()
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        # Kreis
        painter.setBrush(color)
        pen = QtGui.QPen(QtGui.QColor(0,0,0,30))
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.drawEllipse(center, radius, radius)
        # Zahl (klein, mittig)
        if text:
            font = painter.font()
            font.setPointSizeF(max(8.0, font.pointSizeF()))
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QtGui.QPen(QtGui.QColor("#000000")))
            rect = QtCore.QRectF(center.x()-radius, center.y()-radius, radius*2, radius*2)
            painter.drawText(rect, Qt.AlignCenter, text)
        painter.restore()

    def paint(self, painter: QtGui.QPainter, option: QtWidgets.QStyleOptionViewItem, index: QtCore.QModelIndex):
        view = option.widget  # QTreeWidget
        is_top = not index.parent().isValid()  # True = Task (Top-Level)

        if is_top and index.column() == 0:
            painter.save()

            # Zeilenrechteck über ALLE Spalten bestimmen
            row_rect = option.rect
            last_col = view.columnCount() - 1
            last_rect = view.visualRect(view.model().index(index.row(), last_col, index.parent()))
            full_rect = QtCore.QRect(row_rect.left(), row_rect.top(),
                                     last_rect.right() - row_rect.left(), row_rect.height())

            # Innenabstand für "Karten"-Look
            inset = 6
            card_rect = full_rect.adjusted(inset, 4, -inset, -4)

            # Karte
            path = QtGui.QPainterPath()
            path.addRoundedRect(card_rect, 12, 12)
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            painter.fillPath(path, QtGui.QColor("#FFFFFF"))

            # feine Kontur + zarter Schatteneffekt
            pen = QtGui.QPen(QtGui.QColor("#E5E7EB"))
            pen.setWidthF(1.0)
            painter.setPen(pen)
            painter.drawPath(path)

            # leichte Top-Highlight-Linie (Optik)
            top_line = QtCore.QLineF(card_rect.left()+1, card_rect.top()+1, card_rect.right()-1, card_rect.top()+1)
            painter.setPen(QtGui.QPen(QtGui.QColor(0,0,0,12)))
            painter.drawLine(top_line)

            painter.restore()

        # Standard-Text/Icons etc. malen
        super().paint(painter, option, index)

        # Nach dem Standard-Draw die Indikatoren rechts einzeichnen (nur Top-Level, Spalte 0)
        if is_top and index.column() == 0:
            item = view.itemFromIndex(index)
            counts: Optional[Dict[str, int]] = item.data(0, Qt.UserRole + 1)
            if counts:
                painter.save()
                painter.setRenderHint(QtGui.QPainter.Antialiasing, True)

                # Fläche der Karte erneut bestimmen
                row_rect = option.rect
                last_col = view.columnCount() - 1
                last_rect = view.visualRect(view.model().index(index.row(), last_col, index.parent()))
                full_rect = QtCore.QRect(row_rect.left(), row_rect.top(),
                                         last_rect.right() - row_rect.left(), row_rect.height())
                inset = 6
                card_rect = full_rect.adjusted(inset, 4, -inset, -4)

                # Rechtsbündige Anordnung der vier Punkte
                radius = 9.0
                gap = 10.0
                cx_right = card_rect.right() - 14 - radius  # 14px Innenabstand rechts
                cy = card_rect.center().y()

                centers = [
                    QtCore.QPointF(cx_right - (radius*2 + gap)*3, cy),  # ToDo
                    QtCore.QPointF(cx_right - (radius*2 + gap)*2, cy),  # Warten
                    QtCore.QPointF(cx_right - (radius*2 + gap)*1, cy),  # On Hold
                    QtCore.QPointF(cx_right - (radius*2 + gap)*0, cy),  # Done
                ]

                # Reihenfolge: ToDo | Warten | On Hold | Done
                self._draw_indicator(painter, centers[0], radius, self.COLOR_TODO,   str(counts.get("todo", 0)) if counts.get("todo", 0) else "")
                self._draw_indicator(painter, centers[1], radius, self.COLOR_WAIT,   str(counts.get("waiting", 0)) if counts.get("waiting", 0) else "")
                self._draw_indicator(painter, centers[2], radius, self.COLOR_ONHOLD, str(counts.get("onhold", 0)) if counts.get("onhold", 0) else "")
                self._draw_indicator(painter, centers[3], radius, self.COLOR_DONE,   str(counts.get("done", 0)) if counts.get("done", 0) else "")

                painter.restore()

    def sizeHint(self, option: QtWidgets.QStyleOptionViewItem, index: QtCore.QModelIndex):
        # Etwas mehr vertikale Luft, damit die Karte „atmen“ kann
        sz = super().sizeHint(option, index)
        extra = 8 if not index.parent().isValid() else 4
        return QtCore.QSize(sz.width(), sz.height() + extra)


if __name__ == "__main__":
    main()
