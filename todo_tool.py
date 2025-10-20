#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ToDo Tool (Deutsch) – PySide6 (Variante C: Gradient NUR im Aufgabenbereich)
- Aufgaben mit Titel, Beschreibung, Priorität, Status, 1–n Subtasks, Finished Date
- JSON-Persistenz (bei jeder Änderung speichern und UI neu laden)
- Filter und Sortierung (Status / Priorität / Titel / Datum)
- Export: Alle im aktuellen Monat auf "Done" gesetzten Tasks (inkl. Subtasks)
- Schöne, moderne Oberfläche; **schwarzer Text**; **pastelliger Verlauf nur im Tree-Bereich**

Voraussetzungen:
    pip install PySide6

Start:
    python todo_tool_gradient_C.py
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt

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


def iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class Subtask:
    title: str
    description: str = ""
    status: str = "ToDo"
    finished_date: Optional[str] = None

    def normalize(self):
        if self.status not in STATI:
            self.status = "ToDo"
        if self.status != "Done":
            self.finished_date = None
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
        if not self.subtasks:
            if self.status == "Done":
                if not self.finished_date:
                    self.finished_date = iso_now()
            else:
                self.finished_date = None
            return

        sub_statuses = [s.status for s in self.subtasks]
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

        if all(st == "ToDo" for st in sub_statuses):
            self.status = "ToDo"
            self.finished_date = None
            return

        candidates = [st for st in sub_statuses if st not in ("ToDo", "Done")]
        if candidates:
            candidates.sort(key=lambda s: STATUS_PRIORITY_ORDER.index(s))
            dominant = candidates[-1]
            self.status = dominant
        else:
            self.status = "On Hold"
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
        self.setMinimumWidth(520)

        self.title_edit = QtWidgets.QLineEdit()
        self.desc_edit = QtWidgets.QPlainTextEdit()
        self.prio_combo = QtWidgets.QComboBox()
        self.prio_combo.addItems(PRIOS)

        self.status_combo = QtWidgets.QComboBox()
        self.status_combo.addItems(STATI)

        form = QtWidgets.QFormLayout()
        form.addRow("Titel:", self.title_edit)
        form.addRow("Beschreibung:", self.desc_edit)
        form.addRow("Priorität:", self.prio_combo)
        form.addRow("Status:", self.status_combo)

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
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
        self.setMinimumWidth(480)

        self.title_edit = QtWidgets.QLineEdit()
        self.desc_edit = QtWidgets.QPlainTextEdit()
        self.status_combo = QtWidgets.QComboBox()
        self.status_combo.addItems(STATI)

        form = QtWidgets.QFormLayout()
        form.addRow("Titel:", self.title_edit)
        form.addRow("Beschreibung:", self.desc_edit)
        form.addRow("Status:", self.status_combo)

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(btns)

        self._subtask = subtask
        if subtask:
            self.title_edit.setText(subtask.title)
            self.desc_edit.setPlainText(subtask.description)
            self.status_combo.setCurrentIndex(max(STATI.index(subtask.status), 0))

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
        return s.normalize()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1100, 700)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setColumnCount(6)
        self.tree.setHeaderLabels(["Titel", "Beschreibung", "Priorität", "Status", "Fertig am", "Typ"])
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tree.setUniformRowHeights(True)
        self.tree.setAnimated(True)
        self.tree.setIndentation(24)
        self.setCentralWidget(self.tree)

        self._create_actions()
        self._create_toolbar()
        self._create_filter_panel()

        self.statusBar().showMessage("Bereit")

        self._apply_styles()

        self.path = Path(JSON_FILE)
        self.tasks: List[Task] = []
        self.load_and_refresh()

        self.tree.itemDoubleClicked.connect(self.edit_selected_item)

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
        self.filter_status.currentIndexChanged.connect(self.refresh_tree_view)
        hl.addWidget(self.filter_status)

        hl.addWidget(QtWidgets.QLabel("Filter Prio:"))
        self.filter_prio = QtWidgets.QComboBox()
        self.filter_prio.addItem("Alle")
        self.filter_prio.addItems(PRIOS)
        self.filter_prio.currentIndexChanged.connect(self.refresh_tree_view)
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
            QMainWindow {
                background: #FFFFFF;
                color: #000000;
            }
            QDockWidget {
                background: #FFFFFF;
                color: #000000;
                border: 1px solid #E5E7EB;
            }
            QLabel {
                color: #000000;
                font-weight: 600;
            }
            QLineEdit, QPlainTextEdit, QComboBox {
                background: #FFFFFF;
                color: #000000;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 6px 8px;
                selection-background-color: #D0E7FF;
                selection-color: #000000;
            }
            QToolBar {
                background: #FFFFFF;
                spacing: 6px;
                padding: 6px;
                border-bottom: 1px solid #E5E7EB;
            }
            QToolButton {
                color: #000000;
                background: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 10px;
                padding: 6px 10px;
            }
            QToolButton:hover { background: #F5F7FA; }
            QToolButton:pressed { background: #EDF1F5; }

            QHeaderView::section {
                background: #FFFFFF;
                color: #000000;
                padding: 8px;
                border: none;
                border-bottom: 1px solid #E5E7EB;
            }

            /* Pastell-Gradient NUR im Tree-Widget */
            QTreeWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0   #f8a1c4,
                    stop:0.25 #ffd7a8,
                    stop:0.5  #fff2b3,
                    stop:0.75 #c8f3e1,
                    stop:1    #cde7ff
                );
                color: #000000;
                border: none;
            }
            QTreeView::item:hover {
                background: rgba(0,0,0,0.04);
            }
            QTreeView::item:selected {
                background: rgba(30, 144, 255, 0.25);
                color: #000000;
            }

            QDialog {
                background: #FFFFFF;
                color: #000000;
            }
            QDialog QPushButton {
                background: #FFFFFF;
                color: #000000;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 6px 12px;
            }
            QDialog QPushButton:hover { background: #F5F7FA; }

            QStatusBar { color: #000000; }
        """)

    def load_and_refresh(self):
        self.tasks = load_tasks(self.path)
        self.refresh_tree_view()

    def persist_and_reload(self):
        save_tasks(self.path, self.tasks)
        self.load_and_refresh()

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

            for s in t.subtasks:
                child = QtWidgets.QTreeWidgetItem([
                    s.title, s.description, "", s.status, s.finished_date or "", "Subtask"
                ])
                child.setData(0, Qt.UserRole, ("subtask", id(t), id(s)))
                top.addChild(child)

            self.tree.addTopLevelItem(top)
            self.tree.expandItem(top)

        self.tree.resizeColumnToContents(0)
        self.tree.resizeColumnToContents(2)
        self.tree.resizeColumnToContents(3)
        self.tree.setColumnWidth(1, 420)

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
        if sel[0] == "task":
            task = self.find_task_by_id(sel[1])
        else:
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
                    s.set_status("Done")
                task.recompute_status_from_subtasks()
            else:
                task.set_status("Done")
            self.persist_and_reload()
        elif sel[0] == "subtask":
            task = self.find_task_by_id(sel[1])
            sub = self.find_subtask_by_id(task, sel[2]) if task else None
            if not task or not sub:
                return
            sub.set_status("Done")
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
                    {"title": "Recherche", "description": "Infos sammeln", "status": "ToDo", "finished_date": None},
                    {"title": "Kontakt aufnehmen", "description": "E-Mail schreiben", "status": "Warte auf Antwort", "finished_date": None},
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


if __name__ == "__main__":
    main()
