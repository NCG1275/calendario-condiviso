import sys
import re
import json
import os
import shutil
from pathlib import Path
from datetime import date, timedelta
from typing import List, Tuple

from PySide6.QtCore import Qt, Signal, QTimer, QSignalBlocker, QSettings
from PySide6.QtGui import QColor, QPalette, QCloseEvent, QTextCursor, QPen, QBrush
from PySide6.QtWidgets import (
    QAbstractItemDelegate,
    QApplication,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QPlainTextEdit,
    QStyledItemDelegate,
    QVBoxLayout,
    QHBoxLayout,
    QSizePolicy,
    QToolButton,
    QHeaderView,
    QWidget,
    QSplitter,
)

# ----------------------------
# Config dati
# ----------------------------

APP_NAME = "Planner Turni Medici"
APP_VERSION = "v0.1 beta"
APP_AUTHOR = "GN Aru"
APP_SETTINGS_ORG = "PlannerTurni"
APP_SETTINGS_APP = "PlannerTurniMedici"

DAYS = ["h", "Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]

DOCTORS = [
    "Aru", "Cabianca", "Casula", "Corda", "Del Rio", "Desogus", "Masillo",
    "Mattana", "Pili", "Piras D", "Piras F", "Pistincu", "Pitzalis",
    "Puddu", "Sanna", "Tolu"
]
NON_ANALYSIS_DOCTORS = ["Finco"]
EXTRA_ROWS = ["rep. giorno", "rep. notte"]
TABLE_DOCTORS = DOCTORS + NON_ANALYSIS_DOCTORS
DOCTOR_ROWS_COUNT = len(TABLE_DOCTORS)
EXTRA_START_ROW = DOCTOR_ROWS_COUNT

# Turni ammessi e durata in ore
SHIFT_HOURS = {
    "8-14": 6,
    "8-15": 7,
    "14-20": 6,
    "8-20": 12,
    "20-24": 4,
    "0-8": 8,
    "8-16": 8
}
SHIFT_SHORTCUTS = {
    "14": "14-20",
    "20": "20-24",
    "814": "8-14",
    "815": "8-15",
    "816": "8-16",
    "820": "8-20",
}
ZERO_HOUR_LABELS = {"rs", "PT", "ro", "RF"}
ZERO_HOUR_LABELS_CASEFOLD = {label.casefold(): label for label in ZERO_HOUR_LABELS}
SPECIAL_HOUR_LABELS = {"aggp": 7, "cs": 7, "c": 7, "f": 7.36, "m": 6}
SPECIAL_HOUR_LABELS_CASEFOLD = {label.casefold(): label for label in SPECIAL_HOUR_LABELS}
DEST_LABELS = {
    "ORTO",
    "VASC",
    "CALÃ’",
    "ZORCOLO",
    "PISANU",
    "SG",
    "G",
    "END",
    "EMO",
    "GPO",
    "DS",
    "ORL",
    "ORL.PED",
    "PLASTICA",
    "PLAST",
    "OCUL.PED",
    "OCUL.POL",
}  # TODO: incollare lista reale
DEST_LABELS_CASEFOLD = {label.casefold(): label for label in DEST_LABELS}
DEST_SHORTCUTS = {
    "c": "CALÃ’",
    "e": "END",
    "oc": "OCUL.POL",
    "op": "OCUL.PED",
    "o": "ORTO",
    "p": "PISANU",
    "pl": "PLAST",
    "v": "VASC",
    "z": "ZORCOLO",
    "orlp": "ORL.PED",
}
DEST_SHORTCUTS_CASEFOLD = {alias.casefold(): target for alias, target in DEST_SHORTCUTS.items()}
PINK_BG = QColor(255, 220, 220)
ORANGE_BG = QColor(255, 235, 180)
WHITE_BG = QColor(255, 255, 255)
STATS_BLUE_BG = QColor(11, 79, 162)
STATS_BLUE_BG_ALT = QColor(9, 61, 124)
STATS_TEXT_FG = QColor(255, 255, 255)
# Su alcuni build Windows gli header possono non rispettare bene il paint del background:
# usiamo una combinazione ad alto contrasto per evitare testo "invisibile".
if sys.platform.startswith("win"):
    HEADER_BLUE_BG = QColor(205, 225, 245)
    HEADER_TEXT_FG = QColor(20, 20, 20)
else:
    HEADER_BLUE_BG = QColor(11, 79, 162)
    HEADER_TEXT_FG = QColor(255, 255, 255)
ZERO_HOUR_STRIPE_BRUSH = QBrush(QColor(225, 225, 225), Qt.BDiagPattern)
DEST_REQUIRED_ERROR = "Riga 2: manca destinazione"
ERROR_CELL_ROLE = Qt.UserRole + 10
DEST_REQUIRED_LINE2_ROLE = Qt.UserRole + 11

LINE2_YELLOW = QColor(255, 245, 170)
LINE2_GREEN = QColor(190, 235, 190)
LINE2_AZZURRO = QColor(175, 225, 255)
LINE2_CELESTE = QColor(190, 240, 255)
LINE2_VIOLA = QColor(220, 190, 245)
LINE2_ARANCIO = QColor(255, 210, 160)
LINE2_GRIGIO = QColor(220, 220, 220)
LINE2_MARRONE = QColor(210, 175, 145)
LINE2_ROSSO = QColor(255, 175, 175)

DEST_LINE2_COLORS = {
    "g": LINE2_YELLOW,
    "gpo": LINE2_YELLOW,
    "orto": LINE2_GREEN,
    "vasc": LINE2_AZZURRO,
    "pisanu": LINE2_CELESTE,
    "orl": LINE2_VIOLA,
    "orl.ped": LINE2_VIOLA,
    "end": LINE2_ARANCIO,
    "zorcolo": LINE2_GRIGIO,
    "sg": LINE2_GRIGIO,
    "ocul.ped": LINE2_GRIGIO,
    "ocul.pol": LINE2_GRIGIO,
    "ds": LINE2_MARRONE,
    "calÃ²": LINE2_ROSSO,
}

# accetta: "8-14", "8 - 14", "8-14**", "8-14 **"
SHIFT_RE = re.compile(r"^\s*(\d{1,2}\s*-\s*\d{1,2})\s*(\*\*)?\s*$")
DATA_FILE = Path(__file__).resolve().parent / "planner_data.json"


def _user_data_file_path() -> Path:
    if sys.platform == "darwin":
        base_dir = Path.home() / "Library" / "Application Support" / "PlannerTurni"
    elif sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA", "").strip()
        if appdata:
            base_dir = Path(appdata) / "PlannerTurni"
        else:
            base_dir = Path.home() / "AppData" / "Roaming" / "PlannerTurni"
    else:
        base_dir = Path.home() / ".local" / "share" / "planner_turni"
    return base_dir / "planner_data.json"


def _week_count_in_json(path: Path) -> int:
    try:
        if not path.exists() or not path.is_file():
            return -1
        raw = path.read_text(encoding="utf-8-sig")
        data = json.loads(raw)
        weeks = data.get("weeks", {})
        if isinstance(weeks, dict):
            return len(weeks)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        pass
    return -1


def resolve_data_file() -> Path:
    override = os.environ.get("PLANNER_DATA_FILE", "").strip()
    if override:
        return Path(override).expanduser()

    user_path = _user_data_file_path()
    # In eseguibile distribuito, salva sempre accanto al file .exe.
    if bool(getattr(sys, "frozen", False)):
        return Path(sys.executable).resolve().parent / "planner_data.json"
    candidate_paths = []
    for candidate in (
        DATA_FILE,
        Path.cwd() / "planner_data.json",
        Path(sys.argv[0]).resolve().parent / "planner_data.json" if sys.argv and sys.argv[0] else None,
        Path(sys.executable).resolve().parent / "planner_data.json",
        user_path,
    ):
        if candidate is None:
            continue
        if candidate not in candidate_paths:
            candidate_paths.append(candidate)

    best_existing = None
    best_weeks = -1
    for candidate in candidate_paths:
        weeks = _week_count_in_json(candidate)
        if weeks > best_weeks:
            best_weeks = weeks
            best_existing = candidate

    if best_existing is not None and best_weeks >= 0:
        if best_existing.exists() and os.access(best_existing, os.W_OK):
            return best_existing
        if (not best_existing.exists()) and os.access(best_existing.parent, os.W_OK):
            return best_existing

    fallback_path = user_path
    if best_existing is not None and best_existing.exists() and best_existing != fallback_path and not fallback_path.exists():
        try:
            fallback_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(best_existing, fallback_path)
        except OSError:
            pass
    return fallback_path


def get_max_iso_weeks(year: int) -> int:
    return date(year, 12, 28).isocalendar().week


def get_week_key(year: int, week_index: int) -> str:
    return f"{year}-W{week_index:02d}"


def get_week_dates_iso(year: int, week_index: int) -> List[date]:
    monday = date.fromisocalendar(year, week_index, 1)
    return [monday + timedelta(days=offset) for offset in range(7)]


def parse_week_key(week_key: str) -> Tuple[int, int] | None:
    m = re.match(r"^(\d{4})-W(\d{2})$", week_key)
    if not m:
        return None
    year = int(m.group(1))
    week_index = int(m.group(2))
    try:
        date.fromisocalendar(year, week_index, 1)
    except ValueError:
        return None
    return year, week_index


def count_filled_cells_in_week_payload(payload: dict) -> int:
    if not isinstance(payload, dict):
        return 0
    cells = payload.get("cells", {})
    if not isinstance(cells, dict):
        return 0

    filled = 0
    for day_map in cells.values():
        if not isinstance(day_map, dict):
            continue
        for day_payload in day_map.values():
            if isinstance(day_payload, dict):
                shift = str(day_payload.get("shift", "")).strip()
                dest = str(day_payload.get("dest", "")).strip()
                if shift or dest:
                    filled += 1
            elif str(day_payload).strip():
                filled += 1
    return filled


def normalize_dest_label(value: str) -> str:
    token = value.strip()
    if not token:
        return ""
    shortcut_expanded = DEST_SHORTCUTS_CASEFOLD.get(token.casefold(), token)
    return DEST_LABELS_CASEFOLD.get(shortcut_expanded.casefold(), "")


def autocomplete_dest_line(dest_line: str) -> str:
    token = dest_line.strip()
    if not token:
        return ""
    if "+" not in token:
        return normalize_dest_label(token) or token.upper()

    parts = [part.strip() for part in token.split("+")]
    if not parts:
        return token
    completed = [normalize_dest_label(part) or part.upper() for part in parts]
    return "+".join(completed)


def autocomplete_shift_line(shift_line: str) -> str:
    token = shift_line.strip()
    if not token:
        return ""
    has_flag = token.endswith("**")
    base = token[:-2].strip() if has_flag else token
    completed = SHIFT_SHORTCUTS.get(base.casefold(), base)
    if has_flag and completed in SHIFT_HOURS:
        return f"{completed}**"
    return completed


def destination_shortcuts_legend_text() -> str:
    lines = [f"{alias.upper()} = {target}" for alias, target in sorted(DEST_SHORTCUTS.items(), key=lambda it: it[0].casefold())]
    return "\n".join(lines)


def normalize_zero_hour_label(value: str) -> str:
    return ZERO_HOUR_LABELS_CASEFOLD.get(value.strip().casefold(), "")


def normalize_special_hour_label(value: str) -> str:
    return SPECIAL_HOUR_LABELS_CASEFOLD.get(value.strip().casefold(), "")


# ----------------------------
# Delegate multilinea con evento live
# ----------------------------

class TwoLineEdit(QPlainTextEdit):
    max_lines_reached = Signal()
    commit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._max_lines = 2
        palette = self.palette()
        palette.setColor(QPalette.Base, QColor(255, 255, 255))
        palette.setColor(QPalette.Text, QColor(0, 0, 0))
        self.setPalette(palette)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setCenterOnScroll(False)
        self.setFrameShape(QPlainTextEdit.NoFrame)
        self.setViewportMargins(0, 0, 0, 0)
        self.document().setDocumentMargin(0)

    def _line_count_after_insert(self, inserted_text: str) -> int:
        cursor = self.textCursor()
        current_text = self.toPlainText()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        next_text = current_text[:start] + inserted_text + current_text[end:]
        normalized = next_text.replace("\r\n", "\n").replace("\r", "\n")
        return normalized.count("\n") + 1

    def set_max_lines(self, max_lines: int) -> None:
        self._max_lines = max(1, int(max_lines))

    def _reject_third_line(self):
        QApplication.beep()
        self.max_lines_reached.emit()

    def _first_line_is_zero_hour_label(self) -> bool:
        lines = self.toPlainText().splitlines()
        first_line = lines[0].strip() if lines else ""
        if first_line.endswith("**"):
            first_line = first_line[:-2].strip()
        return bool(normalize_zero_hour_label(first_line))

    def _first_line_is_special_hour_label(self) -> bool:
        lines = self.toPlainText().splitlines()
        first_line = lines[0].strip() if lines else ""
        if first_line.endswith("**"):
            first_line = first_line[:-2].strip()
        return bool(normalize_special_hour_label(first_line))

    def _first_line_is_single_line_shift(self) -> bool:
        lines = self.toPlainText().splitlines()
        first_line = lines[0].strip() if lines else ""
        if not first_line:
            return False
        completed = autocomplete_shift_line(first_line)
        base = completed[:-2].strip() if completed.endswith("**") else completed.strip()
        m = SHIFT_RE.match(base)
        if not m:
            return False
        shift = m.group(1).replace(" ", "")
        return shift in {"20-24", "0-8"}

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            modifiers = event.modifiers()
            if modifiers & Qt.ControlModifier:
                self.commit_requested.emit()
                return
            if modifiers & Qt.ShiftModifier:
                if self._line_count_after_insert("\n") > self._max_lines:
                    self._reject_third_line()
                    return
                super().keyPressEvent(event)
                return
            if (
                self._first_line_is_zero_hour_label()
                or self._first_line_is_special_hour_label()
                or self._first_line_is_single_line_shift()
            ):
                self.commit_requested.emit()
                return
            if self._line_count_after_insert("\n") <= self._max_lines:
                super().keyPressEvent(event)
                return
            self.commit_requested.emit()
            return
        super().keyPressEvent(event)

    def insertFromMimeData(self, source):
        text = source.text()
        if text and self._line_count_after_insert(text) > self._max_lines:
            self._reject_third_line()
            return
        super().insertFromMimeData(source)


class DoctorHeaderView(QHeaderView):
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self._error_rows: set[int] = set()

    def set_error_rows(self, rows: set[int]) -> None:
        self._error_rows = set(rows)
        self.viewport().update()

    def paintSection(self, painter, rect, logicalIndex):
        super().paintSection(painter, rect, logicalIndex)
        if logicalIndex in self._error_rows:
            painter.save()
            pen = QPen(QColor(190, 30, 30))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(rect.adjusted(1, 1, -2, -2))
            painter.restore()


class DayHeaderView(QHeaderView):
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self._error_cols: set[int] = set()

    def set_error_cols(self, cols: set[int]) -> None:
        self._error_cols = set(cols)
        self.viewport().update()

    def paintSection(self, painter, rect, logicalIndex):
        super().paintSection(painter, rect, logicalIndex)
        if logicalIndex in self._error_cols:
            painter.save()
            pen = QPen(QColor(190, 30, 30))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(rect.adjusted(1, 1, -2, -2))
            painter.restore()


class MultilineDelegate(QStyledItemDelegate):
    text_live_changed = Signal(int, int, str)  # row, col, text
    max_lines_reached = Signal()

    def createEditor(self, parent, option, index):
        editor = TwoLineEdit(parent)
        if index.row() >= EXTRA_START_ROW:
            editor.set_max_lines(1)
        editor.setTabChangesFocus(True)  # TAB cambia cella
        editor.setFixedHeight(option.rect.height())
        editor.textChanged.connect(lambda: self._on_text_changed(index, editor))
        editor.max_lines_reached.connect(self.max_lines_reached.emit)
        editor.commit_requested.connect(lambda: self._commit_and_close(editor))
        return editor

    def setEditorData(self, editor, index):
        with QSignalBlocker(editor):
            editor.setPlainText(index.data() or "")
        editor.moveCursor(QTextCursor.End)
        editor.verticalScrollBar().setValue(0)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.toPlainText())

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        if bool(index.data(DEST_REQUIRED_LINE2_ROLE)):
            half_h = max(1, option.rect.height() // 2)
            overlay_rect = option.rect.adjusted(1, half_h, -1, -1)
            painter.save()
            color = QColor(PINK_BG)
            color.setAlpha(130)
            painter.fillRect(overlay_rect, color)
            painter.restore()

        if bool(index.data(ERROR_CELL_ROLE)):
            painter.save()
            pen = QPen(QColor(190, 30, 30))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(option.rect.adjusted(1, 1, -2, -2))
            painter.restore()

    def _on_text_changed(self, index, editor):
        self.text_live_changed.emit(index.row(), index.column(), editor.toPlainText())

    def _commit_and_close(self, editor):
        self.commitData.emit(editor)
        self.closeEditor.emit(editor, QAbstractItemDelegate.NoHint)


class ShiftTableWidget(QTableWidget):
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not self.state() == QAbstractItemView.EditingState:
            current = self.currentItem()
            if current and bool(current.flags() & Qt.ItemIsEditable):
                self.editItem(current)
                return
        super().keyPressEvent(event)


# ----------------------------
# Main window
# ----------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION} - by {APP_AUTHOR}")
        self.resize(1100, 650)
        self._restored_prev_visible = False
        self._restored_stats_visible = False
        self._restored_splitter_sizes: List[int] = []
        self._prev_panel_last_width = 0
        self._stats_panel_last_width = 0
        self._prev_panel_preferred_width = 420
        self._stats_panel_preferred_width = 210
        self._restore_window_size()
        self._is_loading = False
        self._dirty = False

        today = date.today()
        iso_today = today.isocalendar()
        self._next_week_monday_shift_cache: dict[str, str] = {}
        self._prev_week_sunday_shift_cache: dict[str, str] = {}
        self.data_file = resolve_data_file()
        self.data_file_weeks = _week_count_in_json(self.data_file)
        self.current_year, self.current_week_index = self._startup_week_from_data(
            iso_today.year, iso_today.week
        )

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        self.setCentralWidget(container)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(8)
        controls.addWidget(QLabel("Anno"))
        self.year_spin = QSpinBox()
        self.year_spin.setRange(2020, 2035)
        self.year_spin.setValue(self.current_year)
        controls.addWidget(self.year_spin)
        controls.addWidget(QLabel("Settimana"))
        self.week_spin = QSpinBox()
        self.week_spin.setRange(1, 53)
        self.week_spin.setValue(self.current_week_index)
        controls.addWidget(self.week_spin)
        self.week_range_label = QLabel("")
        controls.addWidget(self.week_range_label)
        self.dest_help_btn = QToolButton(self)
        self.dest_help_btn.setText("?")
        self.dest_help_btn.setToolTip(destination_shortcuts_legend_text())
        self.dest_help_btn.setAutoRaise(True)
        self.dest_help_btn.setFixedWidth(24)
        self.dest_help_btn.clicked.connect(self.show_dest_shortcuts_popup)
        controls.addWidget(self.dest_help_btn)
        self.export_doc_btn = QToolButton(self)
        self.export_doc_btn.setText("Export DOC")
        self.export_doc_btn.setToolTip("Esporta la settimana corrente in formato DOC (A4)")
        self.export_doc_btn.clicked.connect(self.export_main_week_doc)
        controls.addWidget(self.export_doc_btn)
        controls.addStretch()
        layout.addLayout(controls)

        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(8)
        self.prev_toggle_btn = QToolButton(self)
        self.prev_toggle_btn.setArrowType(Qt.LeftArrow)
        self.prev_toggle_btn.setToolTip("Mostra settimana precedente")
        self.prev_toggle_btn.setAutoRaise(True)
        self.prev_toggle_btn.setFixedWidth(22)
        self.prev_toggle_btn.clicked.connect(self.toggle_prev_panel)
        content.addWidget(self.prev_toggle_btn)

        self.main_splitter = QSplitter(Qt.Horizontal, self)
        self.main_splitter.setChildrenCollapsible(True)
        self.main_splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        content.addWidget(self.main_splitter, stretch=1)

        prev_panel = QWidget(self)
        self.prev_panel = prev_panel
        prev_layout = QVBoxLayout(prev_panel)
        prev_layout.setContentsMargins(0, 0, 0, 0)
        prev_layout.setSpacing(6)
        self.prev_title = QLabel("Settimana precedente")
        self.prev_table = QTableWidget()
        self.prev_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.prev_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.prev_table.setFocusPolicy(Qt.NoFocus)
        self.prev_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        prev_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        prev_layout.addWidget(self.prev_title)
        prev_layout.addWidget(self.prev_table)
        self.main_splitter.addWidget(prev_panel)

        main_panel = QWidget(self)
        self.main_panel = main_panel
        main_layout = QVBoxLayout(main_panel)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)
        self.main_title = QLabel("Settimana corrente")
        self.table = ShiftTableWidget()
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_layout.addWidget(self.main_title)
        main_layout.addWidget(self.table)
        self.main_splitter.addWidget(main_panel)

        stats_panel = QWidget(self)
        self.stats_panel = stats_panel
        stats_layout = QVBoxLayout(stats_panel)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(6)
        self.stats_title = QLabel("Statistiche")
        self.stats_table = QTableWidget()
        self.stats_table.setColumnCount(3)
        self.stats_table.setRowCount(0)
        self.stats_table.setHorizontalHeaderLabels(["GN", "GW", "P"])
        gn_header = self.stats_table.horizontalHeaderItem(0)
        gw_header = self.stats_table.horizontalHeaderItem(1)
        p_header = self.stats_table.horizontalHeaderItem(2)
        if gn_header:
            gn_header.setToolTip("Guardie notturne")
        if gw_header:
            gw_header.setToolTip("Guardie weekend")
        if p_header:
            p_header.setToolTip("Turni a progetto")
        self.stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.stats_table.horizontalHeader().setStretchLastSection(False)
        self.stats_table.verticalHeader().setVisible(True)
        self.stats_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.stats_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.stats_table.setFocusPolicy(Qt.NoFocus)
        self.stats_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.stats_table.setStyleSheet(
            "QTableWidget {"
            " background-color: #0B4FA2;"
            " color: #FFFFFF;"
            " gridline-color: #6FA8FF;"
            " selection-background-color: #0A3D80;"
            " selection-color: #FFFFFF;"
            "}"
            "QHeaderView::section {"
            " background-color: #0A3D80;"
            " color: #FFFFFF;"
            " border: 1px solid #6FA8FF;"
            " padding: 2px;"
            "}"
            "QTableCornerButton::section {"
            " background-color: #0A3D80;"
            " border: 1px solid #6FA8FF;"
            "}"
        )
        stats_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        stats_layout.addWidget(self.stats_title)
        stats_layout.addWidget(self.stats_table)
        self.main_splitter.addWidget(stats_panel)

        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setStretchFactor(2, 0)

        self.stats_toggle_btn = QToolButton(self)
        self.stats_toggle_btn.setArrowType(Qt.RightArrow)
        self.stats_toggle_btn.setToolTip("Mostra statistiche")
        self.stats_toggle_btn.setAutoRaise(True)
        self.stats_toggle_btn.setFixedWidth(22)
        self.stats_toggle_btn.clicked.connect(self.toggle_stats_panel)
        content.addWidget(self.stats_toggle_btn)

        layout.addLayout(content, 1)
        title_h = self.fontMetrics().height() + 6
        for lbl in (self.prev_title, self.main_title, self.stats_title):
            lbl.setFixedHeight(title_h)
            lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.prev_panel.setVisible(False)
        self.stats_panel.setVisible(False)
        self.main_splitter.setSizes([0, 1000, 0])
        self.main_splitter.splitterMoved.connect(self._on_main_splitter_moved)

        self.statusBar()
        self.data_file_label = QLabel(f"Dati: {self.data_file} (weeks: {max(self.data_file_weeks, 0)})")
        self.data_file_label.setToolTip(str(self.data_file))
        self.statusBar().addPermanentWidget(self.data_file_label, 1)
        self.statusBar().showMessage(f"File dati: {self.data_file}", 5000)
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.setInterval(1000)
        self.autosave_timer.timeout.connect(self.save_current_week)

        self._setup_table()
        self.year_spin.valueChanged.connect(self.on_week_selector_changed)
        self.week_spin.valueChanged.connect(self.on_week_selector_changed)
        self._load_selected_week(initial=True)
        QTimer.singleShot(0, self._apply_restored_side_layout)

    def _setup_table(self):
        total_rows = DOCTOR_ROWS_COUNT + len(EXTRA_ROWS)
        stats_rows = len(DOCTORS) + len(EXTRA_ROWS)
        self.table.setRowCount(total_rows)
        self.table.setColumnCount(len(DAYS))
        self.prev_table.setRowCount(total_rows)
        self.prev_table.setColumnCount(len(DAYS))
        self.day_header = DayHeaderView(Qt.Horizontal, self.table)
        self.table.setHorizontalHeader(self.day_header)
        self.doctor_header = DoctorHeaderView(Qt.Vertical, self.table)
        self.table.setVerticalHeader(self.doctor_header)

        self.table.setHorizontalHeaderLabels(DAYS)
        self.table.setVerticalHeaderLabels(TABLE_DOCTORS + ["", ""])
        self.prev_table.setHorizontalHeaderLabels(DAYS)
        self.prev_table.setVerticalHeaderLabels(TABLE_DOCTORS + ["", ""])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.prev_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        for c in range(1, len(DAYS)):
            self.table.horizontalHeader().setSectionResizeMode(c, QHeaderView.Stretch)
            self.prev_table.horizontalHeader().setSectionResizeMode(c, QHeaderView.Stretch)

        # Editing stile Excel
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        two_lines_height = self.table.fontMetrics().lineSpacing() * 2 + 6
        self.table.verticalHeader().setDefaultSectionSize(two_lines_height)
        self.prev_table.verticalHeader().setDefaultSectionSize(two_lines_height)
        self._setup_stats_table_rows(stats_rows, two_lines_height)
        self._setup_prev_table_rows(total_rows, two_lines_height)
        self._fit_prev_panel_width()

        # Crea celle
        for r in range(total_rows):
            for c in range(len(DAYS)):
                item = QTableWidgetItem("")
                item.setTextAlignment(Qt.AlignTop | Qt.AlignLeft)
                item.setBackground(QColor(255, 255, 255))
                item.setForeground(QColor(0, 0, 0))

                # Colonna h: read-only e centrata
                if c == 0:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    item.setTextAlignment(Qt.AlignCenter)
                elif r >= EXTRA_START_ROW:
                    item.setBackground(QColor(245, 245, 245))

                if r >= EXTRA_START_ROW:
                    item.setBackground(QColor(245, 245, 245))
                    if c == 0:
                        item.setText(EXTRA_ROWS[r - EXTRA_START_ROW])
                        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                self.table.setItem(r, c, item)

        # Delegate multilinea per tutte le colonne dei giorni (1..7)
        self.delegate = MultilineDelegate()
        self.delegate.text_live_changed.connect(self.on_text_live_changed)
        self.delegate.max_lines_reached.connect(self.on_max_lines_reached)
        for c in range(1, len(DAYS)):
            self.table.setItemDelegateForColumn(c, self.delegate)

        # Quando una cella viene "committata" (finito l'editing)
        self.table.itemChanged.connect(self.on_item_committed)

        # Inizializza ore
        self.revalidate_week()
        self._set_doctor_headers_bold()

    def toggle_stats_panel(self):
        sizes = self._current_splitter_sizes()
        if not self.stats_panel.isVisible():
            self._fit_stats_panel_width()
            stats_target = self._stats_panel_last_width or self._stats_panel_preferred_width
            main_target = max(sizes[1], self.main_panel.width())
            prev_target = sizes[0] if self.prev_panel.isVisible() else 0
            self._resize_window_width(stats_target, anchor_left=False)
            self.stats_panel.setVisible(True)
            QTimer.singleShot(
                0,
                lambda p=prev_target, m=main_target, s=stats_target: self._set_splitter_sizes(p, m, s),
            )
        else:
            stats_current = max(sizes[2], self.stats_panel.width())
            if stats_current > 0:
                self._stats_panel_last_width = stats_current
            main_target = max(sizes[1], self.main_panel.width()) + stats_current
            prev_target = sizes[0] if self.prev_panel.isVisible() else 0
            self.stats_panel.setVisible(False)
            self._resize_window_width(-stats_current, anchor_left=False)
            QTimer.singleShot(
                0,
                lambda p=prev_target, m=main_target: self._set_splitter_sizes(p, m, 0),
            )
        self._sync_side_toggle_buttons()

    def toggle_prev_panel(self):
        sizes = self._current_splitter_sizes()
        if not self.prev_panel.isVisible():
            self._fit_prev_panel_width()
            prev_target = self._prev_panel_last_width or self._prev_panel_preferred_width
            main_target = max(sizes[1], self.main_panel.width())
            stats_target = sizes[2] if self.stats_panel.isVisible() else 0
            self._resize_window_width(prev_target, anchor_left=True)
            self.prev_panel.setVisible(True)
            QTimer.singleShot(
                0,
                lambda p=prev_target, m=main_target, s=stats_target: self._set_splitter_sizes(p, m, s),
            )
        else:
            prev_current = max(sizes[0], self.prev_panel.width())
            if prev_current > 0:
                self._prev_panel_last_width = prev_current
            main_target = max(sizes[1], self.main_panel.width()) + prev_current
            stats_target = sizes[2] if self.stats_panel.isVisible() else 0
            self.prev_panel.setVisible(False)
            self._resize_window_width(-prev_current, anchor_left=True)
            QTimer.singleShot(
                0,
                lambda m=main_target, s=stats_target: self._set_splitter_sizes(0, m, s),
            )
        self._sync_side_toggle_buttons()

    def _current_splitter_sizes(self) -> List[int]:
        sizes = [max(0, int(v)) for v in self.main_splitter.sizes()]
        while len(sizes) < 3:
            sizes.append(0)
        return sizes[:3]

    def _set_splitter_sizes(self, prev_w: int, main_w: int, stats_w: int) -> None:
        prev = max(0, int(prev_w)) if self.prev_panel.isVisible() else 0
        main = max(1, int(main_w))
        stats = max(0, int(stats_w)) if self.stats_panel.isVisible() else 0
        self.main_splitter.setSizes([prev, main, stats])

    def _resize_window_width(self, delta_width: int, anchor_left: bool = False) -> None:
        if delta_width == 0 or self.isMaximized() or self.isFullScreen():
            return
        geom = self.geometry()
        old_width = geom.width()
        new_width = max(self.minimumWidth(), old_width + int(delta_width))
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            if new_width > avail.width():
                new_width = avail.width()
        applied_delta = new_width - old_width
        if applied_delta == 0:
            return
        new_x = geom.x()
        if anchor_left:
            new_x = geom.x() - applied_delta
        if screen is not None:
            avail = screen.availableGeometry()
            min_x = avail.left()
            max_x = avail.right() - new_width + 1
            if max_x < min_x:
                max_x = min_x
            if new_x < min_x:
                new_x = min_x
            if new_x > max_x:
                new_x = max_x
        self.setGeometry(new_x, geom.y(), new_width, geom.height())

    def _on_main_splitter_moved(self, _pos: int, _index: int) -> None:
        sizes = self._current_splitter_sizes()
        if self.prev_panel.isVisible() and sizes[0] > 0:
            self._prev_panel_last_width = sizes[0]
        if self.stats_panel.isVisible() and sizes[2] > 0:
            self._stats_panel_last_width = sizes[2]

    def _sync_side_toggle_buttons(self) -> None:
        if self.prev_panel.isVisible():
            self.prev_toggle_btn.setArrowType(Qt.RightArrow)
            self.prev_toggle_btn.setToolTip("Nascondi settimana precedente")
        else:
            self.prev_toggle_btn.setArrowType(Qt.LeftArrow)
            self.prev_toggle_btn.setToolTip("Mostra settimana precedente")
        if self.stats_panel.isVisible():
            self.stats_toggle_btn.setArrowType(Qt.LeftArrow)
            self.stats_toggle_btn.setToolTip("Nascondi statistiche")
        else:
            self.stats_toggle_btn.setArrowType(Qt.RightArrow)
            self.stats_toggle_btn.setToolTip("Mostra statistiche")

    def _apply_restored_side_layout(self) -> None:
        prev_visible = bool(self._restored_prev_visible)
        stats_visible = bool(self._restored_stats_visible)
        self.prev_panel.setVisible(prev_visible)
        self.stats_panel.setVisible(stats_visible)
        self._sync_side_toggle_buttons()

        prev_w = self._prev_panel_last_width or self._prev_panel_preferred_width
        stats_w = self._stats_panel_last_width or self._stats_panel_preferred_width
        main_w = max(self.main_panel.width(), 600)
        restored = self._restored_splitter_sizes
        if len(restored) == 3:
            prev_w = max(0, int(restored[0]))
            main_w = max(1, int(restored[1]))
            stats_w = max(0, int(restored[2]))
        if not prev_visible:
            prev_w = 0
        if not stats_visible:
            stats_w = 0
        self._set_splitter_sizes(prev_w, main_w, stats_w)
        self._restored_splitter_sizes = []

    def _fit_prev_panel_width(self) -> None:
        h_col_min = 52
        day_col_min = 102
        day_cols = len(DAYS) - 1
        table_width = self.prev_table.frameWidth() * 2
        if self.prev_table.verticalHeader().isVisible():
            table_width += self.prev_table.verticalHeader().width()
        table_width += h_col_min + day_cols * day_col_min
        if self.prev_table.verticalScrollBar().isVisible():
            table_width += self.prev_table.verticalScrollBar().sizeHint().width()
        table_width += self.prev_table.contentsMargins().left() + self.prev_table.contentsMargins().right()
        table_width = max(table_width, 1)
        panel_width = max(table_width, self.prev_title.sizeHint().width())
        self._prev_panel_preferred_width = panel_width
        self.prev_panel.setMinimumWidth(220)
        self.prev_table.setMinimumWidth(220)

    def show_dest_shortcuts_popup(self):
        QMessageBox.information(
            self,
            "Legenda abbreviazioni destinazioni",
            destination_shortcuts_legend_text(),
        )

    def export_main_week_doc(self) -> None:
        week_key = get_week_key(self.current_year, self.current_week_index)
        default_name = f"turni_{week_key}.doc"
        default_path = Path.home() / default_name
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Esporta settimana principale in DOC",
            str(default_path),
            "Documento Word (*.doc);;Rich Text Format (*.rtf)",
        )
        if not file_path:
            return

        output_path = Path(file_path)
        if output_path.suffix.lower() not in {".doc", ".rtf"}:
            output_path = output_path.with_suffix(".doc")

        try:
            output_path.write_text(self._build_main_week_doc_rtf(), encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(
                self,
                "Export DOC",
                f"Errore durante l'esportazione:\n{exc}",
            )
            return

        self.statusBar().showMessage(f"Esportato: {output_path}", 4000)

    def _build_main_week_doc_rtf(self) -> str:
        week_dates = get_week_dates_iso(self.current_year, self.current_week_index)
        week_key = get_week_key(self.current_year, self.current_week_index)
        title = (
            f"Settimana {week_key} "
            f"({week_dates[0].strftime('%d/%m')} - {week_dates[-1].strftime('%d/%m')})"
        )
        generated_on = f"Generato il {date.today().strftime('%d/%m/%Y')}"
        header_lines = [
            "SERVIZIO SANITARIO REGIONE SARDEGNA",
            "AZIENDA OSPEDALIERO - UNIVERSITARIA DI CAGLIARI",
            "U.O.C. DI ANESTESIA RIANIMAZIONE TERAPIA ANTALGICA",
            "Direttore Prof. Gabriele Finco",
        ]
        service_title = "ORARIO DI SERVIZIO"

        headers = ["Medico"]
        for col in range(len(DAYS)):
            header_item = self.table.horizontalHeaderItem(col)
            header_text = (header_item.text() if header_item else DAYS[col]).replace("\n", " ").strip()
            headers.append(header_text)

        rows: List[List[str]] = []
        for row in range(self.table.rowCount()):
            if row < DOCTOR_ROWS_COUNT:
                row_label = TABLE_DOCTORS[row]
            else:
                row_label = EXTRA_ROWS[row - EXTRA_START_ROW]

            row_values = [row_label]
            for col in range(len(DAYS)):
                item = self.table.item(row, col)
                if row >= EXTRA_START_ROW and col == 0:
                    cell_text = ""
                else:
                    cell_text = (item.text() if item else "").strip()
                row_values.append(cell_text)
            rows.append(row_values)

        page_width_twips = 11907
        page_height_twips = 16840
        margin_left = 540
        margin_right = 540
        usable_page_twips = page_width_twips - margin_left - margin_right

        day_cols_count = max(len(headers) - 2, 1)

        def text_units(value: str) -> int:
            lines = [line.strip() for line in value.splitlines() if line.strip()]
            if not lines:
                return 1
            return max(len(line) for line in lines)

        def max_units_for_col(col_idx: int) -> int:
            header_units = text_units(headers[col_idx])
            row_units = max((text_units(row[col_idx]) for row in rows), default=0)
            return max(header_units, row_units, 1)

        doctor_units = max_units_for_col(0)
        h_units = max_units_for_col(1)
        doctor_col = min(max(980 + doctor_units * 18, 1050), 1750)
        h_col = min(max(260 + h_units * 30, 420), 640)

        min_day_width = 360
        min_required_for_days = day_cols_count * min_day_width
        available_for_days = usable_page_twips - doctor_col - h_col
        if available_for_days < min_required_for_days:
            deficit = min_required_for_days - available_for_days
            doctor_reducible = max(doctor_col - 900, 0)
            reduce_doctor = min(deficit, doctor_reducible)
            doctor_col -= reduce_doctor
            deficit -= reduce_doctor
            h_reducible = max(h_col - 320, 0)
            reduce_h = min(deficit, h_reducible)
            h_col -= reduce_h
            available_for_days = usable_page_twips - doctor_col - h_col

        day_units = [max(max_units_for_col(idx), 4) for idx in range(2, len(headers))]
        day_units_sum = sum(day_units) or day_cols_count
        day_widths: List[int] = []
        for units in day_units:
            proposed = (available_for_days * units) // day_units_sum
            day_widths.append(max(min_day_width, proposed))

        adjust = available_for_days - sum(day_widths)
        if day_widths and adjust != 0:
            order = sorted(range(len(day_widths)), key=lambda i: day_units[i], reverse=(adjust > 0))
            step = 1 if adjust > 0 else -1
            guard = 0
            while adjust != 0 and guard < 20000:
                idx = order[guard % len(order)]
                if step < 0 and day_widths[idx] <= 300:
                    guard += 1
                    if guard >= len(order) * 3:
                        break
                    continue
                day_widths[idx] += step
                adjust -= step
                guard += 1

        col_widths = [doctor_col, h_col] + day_widths

        def format_cell_rtf(col_idx: int, raw_value: str) -> str:
            lines = [line.strip() for line in raw_value.splitlines()]
            if col_idx < 2 or len(lines) <= 1:
                return self._rtf_escape(raw_value)
            first_line = self._rtf_escape(lines[0]) if lines else ""
            destination_lines = [self._rtf_escape(line) for line in lines[1:] if line]
            if not destination_lines:
                return first_line
            italic_part = r"\line ".join(rf"\i {line}\i0" for line in destination_lines)
            if first_line:
                return first_line + r"\line " + italic_part
            return italic_part

        def row_to_rtf(cells: List[str], bold_cols: set[int] | None = None) -> str:
            if bold_cols is None:
                bold_cols = set()
            parts = [r"\trowd\trgaph70\trleft0\trrh420"]
            running_x = 0
            border = (
                r"\clbrdrt\brdrs\brdrw10"
                r"\clbrdrl\brdrs\brdrw10"
                r"\clbrdrb\brdrs\brdrw10"
                r"\clbrdrr\brdrs\brdrw10"
                r"\clNoWrap"
            )
            for width in col_widths:
                running_x += width
                parts.append(f"{border}\\cellx{running_x}")
            parts.append("\n")
            for idx, value in enumerate(cells):
                text = format_cell_rtf(idx, value)
                if idx in bold_cols:
                    parts.append(rf"\intbl\b {text}\b0\cell")
                else:
                    parts.append(rf"\intbl {text}\cell")
            parts.append(r"\row")
            parts.append("\n")
            return "".join(parts)

        header_bold_cols = {
            idx for idx, label in enumerate(headers) if label.split(" ", 1)[0].strip() in DAYS[1:]
        }
        rep_row_start = EXTRA_START_ROW

        doc_parts = [
            r"{\rtf1\ansi\deff0",
            r"{\fonttbl{\f0 Arial;}}",
            rf"\paperw{page_width_twips}\paperh{page_height_twips}\margl{margin_left}\margr{margin_right}\margt720\margb720",
            r"\fs18",
        ]
        for idx, line in enumerate(header_lines):
            if idx < 3:
                doc_parts.append(rf"\pard\qc\b {self._rtf_escape(line)}\b0\par")
            else:
                doc_parts.append(rf"\pard\qc {self._rtf_escape(line)}\par")
        doc_parts.extend([
            rf"\pard\qc\b {self._rtf_escape(service_title)}\b0\par\par",
            rf"\pard\b {self._rtf_escape(title)}\b0\par",
            rf"\pard {self._rtf_escape(generated_on)}\par\par",
            row_to_rtf(headers, bold_cols=header_bold_cols),
        ])
        for row_idx, row_values in enumerate(rows):
            bold_cols = {0}
            if row_idx >= rep_row_start:
                for col_idx, value in enumerate(row_values):
                    if col_idx >= 2 and value.strip():
                        bold_cols.add(col_idx)
            doc_parts.append(row_to_rtf(row_values, bold_cols=bold_cols))
        doc_parts.append("}")
        return "\n".join(doc_parts)

    def _rtf_escape(self, text: str) -> str:
        escaped: List[str] = []
        for ch in text:
            if ch == "\\":
                escaped.append(r"\\")
                continue
            if ch == "{":
                escaped.append(r"\{")
                continue
            if ch == "}":
                escaped.append(r"\}")
                continue
            if ch == "\n":
                escaped.append(r"\line ")
                continue
            code = ord(ch)
            if 32 <= code <= 126:
                escaped.append(ch)
            else:
                signed = code if code <= 32767 else code - 65536
                escaped.append(f"\\u{signed}?")
        return "".join(escaped)

    def _setup_prev_table_rows(self, total_rows: int, row_height: int) -> None:
        for row in range(total_rows):
            self.prev_table.setRowHeight(row, row_height)
            for col in range(self.prev_table.columnCount()):
                item = self.prev_table.item(row, col)
                if item is None:
                    item = QTableWidgetItem("")
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    item.setTextAlignment(Qt.AlignTop | Qt.AlignLeft)
                    self.prev_table.setItem(row, col, item)
                item.setForeground(QColor(0, 0, 0))
                item_font = item.font()
                item_font.setBold(False)
                item.setFont(item_font)
                if col == 0:
                    item.setTextAlignment(Qt.AlignCenter)
                if row >= EXTRA_START_ROW:
                    item.setBackground(QColor(245, 245, 245))
                    if col == 0:
                        item.setText(EXTRA_ROWS[row - EXTRA_START_ROW])
                        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                else:
                    item.setBackground(WHITE_BG)
                    if col == 0:
                        item.setText("")

    def _set_prev_week_headers(self, week_dates: List[date], week_key: str):
        headers = ["h"] + [f"{day}\n{dt.strftime('%d/%m')}" for day, dt in zip(DAYS[1:], week_dates)]
        self.prev_table.setHorizontalHeaderLabels(headers)
        self._style_date_headers(self.prev_table)
        self.prev_title.setText(
            f"Sett. precedente ({week_key}) {week_dates[0].strftime('%d/%m')}-{week_dates[-1].strftime('%d/%m')}"
        )

    def _clear_prev_week_cells(self):
        for row in range(self.prev_table.rowCount()):
            h_item = self.prev_table.item(row, 0)
            if h_item and row < DOCTOR_ROWS_COUNT:
                h_item.setText("")
            for col in range(1, len(DAYS)):
                item = self.prev_table.item(row, col)
                if item:
                    item.setText("")
                    item_font = item.font()
                    item_font.setBold(False)
                    item.setFont(item_font)
                    if row >= EXTRA_START_ROW:
                        item.setBackground(QColor(245, 245, 245))
                    else:
                        item.setBackground(WHITE_BG)

    def _recalculate_prev_week_hours(self) -> None:
        for row in range(DOCTOR_ROWS_COUNT):
            hours = 0.0
            for col in range(1, len(DAYS)):
                item = self.prev_table.item(row, col)
                text = item.text() if item else ""
                shift_line, _ = self._split_cell_lines(text)
                normalized_shift = self._normalize_shift(shift_line)
                if normalized_shift:
                    hours += SHIFT_HOURS.get(normalized_shift, 0)
                    continue
                normalized_special = normalize_special_hour_label(shift_line)
                if normalized_special:
                    hours += SPECIAL_HOUR_LABELS.get(normalized_special, 0)

            h_item = self.prev_table.item(row, 0)
            if h_item:
                h_item.setText(str(int(hours)))

    def _load_previous_week_preview(self, all_data: dict):
        current_monday = date.fromisocalendar(self.current_year, self.current_week_index, 1)
        prev_monday = current_monday - timedelta(days=7)
        prev_iso = prev_monday.isocalendar()
        prev_key = get_week_key(prev_iso.year, prev_iso.week)
        prev_dates = get_week_dates_iso(prev_iso.year, prev_iso.week)
        self._set_prev_week_headers(prev_dates, prev_key)
        self._clear_prev_week_cells()

        week_data = all_data.get("weeks", {}).get(prev_key, {})
        if not isinstance(week_data, dict):
            return

        cells = week_data.get("cells", {})
        if not isinstance(cells, dict):
            return

        doctor_to_row = {doctor: row for row, doctor in enumerate(TABLE_DOCTORS)}
        day_to_col = {day: col for col, day in enumerate(DAYS[1:], start=1)}

        for doctor, day_data in cells.items():
            row = doctor_to_row.get(doctor)
            if row is None or not isinstance(day_data, dict):
                continue
            for day, payload in day_data.items():
                col = day_to_col.get(day)
                if col is None or not isinstance(payload, dict):
                    continue
                shift = str(payload.get("shift", "")).strip()
                dest = str(payload.get("dest", "")).strip()
                flagged = bool(payload.get("flagged", False))
                if flagged and shift and "**" not in shift:
                    shift = f"{shift}**"
                text = shift if not dest else f"{shift}\n{dest}"
                item = self.prev_table.item(row, col)
                if item:
                    item.setText(text)
                    item.setBackground(self._get_cell_background(shift, dest, col))
                    item_font = item.font()
                    item_font.setBold(shift.strip().endswith("**"))
                    item.setFont(item_font)

        extra_rows = week_data.get("extra_rows", {})
        if isinstance(extra_rows, dict):
            extra_to_row = {row_name: EXTRA_START_ROW + i for i, row_name in enumerate(EXTRA_ROWS)}
            day_to_col = {day: col for col, day in enumerate(DAYS[1:], start=1)}
            for row_name, day_data in extra_rows.items():
                row = extra_to_row.get(row_name)
                if row is None or not isinstance(day_data, dict):
                    continue
                for day, payload in day_data.items():
                    col = day_to_col.get(day)
                    if col is None:
                        continue
                    item = self.prev_table.item(row, col)
                    if not item:
                        continue
                    if isinstance(payload, dict):
                        shift = str(payload.get("shift", "")).strip()
                        dest = str(payload.get("dest", "")).strip()
                        text = shift if not dest else f"{shift}\n{dest}"
                    else:
                        text = str(payload) if payload is not None else ""
                    item.setText(text)

        self._recalculate_prev_week_hours()

    def _setup_stats_table_rows(self, total_rows: int, row_height: int) -> None:
        self.stats_table.setRowCount(total_rows)
        self.stats_table.setVerticalHeaderLabels(DOCTORS + ["", ""])
        self.stats_table.verticalHeader().setDefaultSectionSize(row_height)
        for row in range(total_rows):
            self.stats_table.setRowHeight(row, row_height)
            for col in range(self.stats_table.columnCount()):
                item = self.stats_table.item(row, col)
                if item is None:
                    item = QTableWidgetItem("")
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    item.setTextAlignment(Qt.AlignCenter)
                    self.stats_table.setItem(row, col, item)
                item.setText("" if row >= len(DOCTORS) else "0")
                item.setForeground(STATS_TEXT_FG)
                if row >= len(DOCTORS):
                    item.setBackground(STATS_BLUE_BG_ALT)
                else:
                    item.setBackground(STATS_BLUE_BG)
        self._set_doctor_headers_bold()
        self._fit_stats_panel_width()

    def _set_doctor_headers_bold(self) -> None:
        for table in (self.table, self.prev_table, self.stats_table):
            for row in range(table.rowCount()):
                header_item = table.verticalHeaderItem(row)
                if not header_item:
                    continue
                header_font = header_item.font()
                if table is self.stats_table:
                    header_font.setBold(row < len(DOCTORS))
                else:
                    header_font.setBold(row < DOCTOR_ROWS_COUNT)
                    if row < DOCTOR_ROWS_COUNT:
                        header_item.setBackground(HEADER_BLUE_BG)
                        header_item.setForeground(HEADER_TEXT_FG)
                header_item.setFont(header_font)

    def _style_date_headers(self, table: QTableWidget) -> None:
        for col in range(table.columnCount()):
            header_item = table.horizontalHeaderItem(col)
            if not header_item:
                continue
            header_font = header_item.font()
            header_font.setBold(True)
            header_item.setFont(header_font)
            header_item.setBackground(HEADER_BLUE_BG)
            header_item.setForeground(HEADER_TEXT_FG)

    def _fit_stats_panel_width(self) -> None:
        self.stats_table.resizeColumnsToContents()
        table_width = self.stats_table.frameWidth() * 2
        if self.stats_table.verticalHeader().isVisible():
            table_width += self.stats_table.verticalHeader().width()
        for col in range(self.stats_table.columnCount()):
            table_width += self.stats_table.columnWidth(col)
        if self.stats_table.verticalScrollBar().isVisible():
            table_width += self.stats_table.verticalScrollBar().sizeHint().width()
        table_width += self.stats_table.contentsMargins().left() + self.stats_table.contentsMargins().right()
        table_width = max(table_width, 1)
        panel_width = max(table_width, self.stats_title.sizeHint().width())
        self._stats_panel_preferred_width = panel_width
        self.stats_panel.setMinimumWidth(170)
        self.stats_table.setMinimumWidth(170)

    def _set_week_headers(self, week_dates: List[date]):
        headers = ["h"] + [f"{day}\n{dt.strftime('%d/%m')}" for day, dt in zip(DAYS[1:], week_dates)]
        self.table.setHorizontalHeaderLabels(headers)
        self._style_date_headers(self.table)
        self.main_title.setText(
            f"Settimana corrente {week_dates[0].strftime('%d/%m')}-{week_dates[-1].strftime('%d/%m')}"
        )
        self.week_range_label.setText(f"{week_dates[0].strftime('%d/%m')}â€“{week_dates[-1].strftime('%d/%m')}")

    def _normalize_week_for_year(self):
        year = self.year_spin.value()
        max_week = get_max_iso_weeks(year)
        if self.week_spin.value() > max_week:
            self.week_spin.blockSignals(True)
            self.week_spin.setValue(max_week)
            self.week_spin.blockSignals(False)
        return year, self.week_spin.value()

    def _clear_week_cells(self):
        self._is_loading = True
        self.table.blockSignals(True)
        try:
            for row in range(self.table.rowCount()):
                for col in range(1, len(DAYS)):
                    item = self.table.item(row, col)
                    if item:
                        item.setText("")
        finally:
            self.table.blockSignals(False)
            self._is_loading = False
        self.revalidate_week()

    def on_week_selector_changed(self):
        self._load_selected_week(initial=False)

    def _load_selected_week(self, initial: bool):
        old_key = get_week_key(self.current_year, self.current_week_index)

        year, week_index = self._normalize_week_for_year()
        week_dates = get_week_dates_iso(year, week_index)
        self._set_week_headers(week_dates)

        if not initial and self._dirty:
            self.save_current_week(show_message=False)

        new_key = get_week_key(year, week_index)
        if old_key != new_key:
            self.autosave_timer.stop()

        # Aggiorna subito il contesto settimana, cosÃ¬ la validazione cross-settimana
        # durante load_week/revalidate_week usa l'anno/settimana corretti.
        self.current_year = year
        self.current_week_index = week_index

        all_data = self.load_all()
        week_data = all_data.get("weeks", {}).get(new_key)

        if isinstance(week_data, dict):
            self.load_week(week_data)
            self.statusBar().showMessage(f"Caricato {new_key}", 2000)
        else:
            self._clear_week_cells()
            self._dirty = False
            self.statusBar().showMessage("Nuova settimana (vuota)", 2000)
        self.refresh_night_stats()
        self._load_previous_week_preview(all_data)

    # ----------------------------
    # Parsing e validazione
    # ----------------------------

    def _split_cell_lines(self, text: str) -> Tuple[str, str]:
        lines = text.splitlines()
        shift = lines[0].strip() if lines else ""
        dest = lines[1].strip() if len(lines) > 1 else ""
        return shift, dest

    def _normalize_shift(self, shift_line: str) -> str:
        m = SHIFT_RE.match(shift_line)
        if not m:
            return ""
        shift = m.group(1).replace(" ", "")
        return shift if shift in SHIFT_HOURS else ""

    def _get_next_week_monday_shift_for_doctor(self, row: int) -> str:
        doctor = DOCTORS[row]
        cached = self._next_week_monday_shift_cache.get(doctor)
        if cached is not None:
            return cached

        current_monday = date.fromisocalendar(self.current_year, self.current_week_index, 1)
        next_monday = current_monday + timedelta(days=7)
        next_iso = next_monday.isocalendar()
        next_key = get_week_key(next_iso.year, next_iso.week)

        shift = ""
        week_data = self.load_all().get("weeks", {}).get(next_key, {})
        if isinstance(week_data, dict):
            cells = week_data.get("cells", {})
            if isinstance(cells, dict):
                doctor_data = cells.get(doctor, {})
                if isinstance(doctor_data, dict):
                    monday_payload = doctor_data.get("Lun")
                    if isinstance(monday_payload, dict):
                        raw_shift = str(monday_payload.get("shift", "")).strip()
                        shift = self._normalize_shift(raw_shift)

        self._next_week_monday_shift_cache[doctor] = shift
        return shift

    def _get_prev_week_sunday_shift_for_doctor(self, row: int) -> str:
        doctor = DOCTORS[row]
        cached = self._prev_week_sunday_shift_cache.get(doctor)
        if cached is not None:
            return cached

        current_monday = date.fromisocalendar(self.current_year, self.current_week_index, 1)
        prev_sunday = current_monday - timedelta(days=1)
        prev_iso = prev_sunday.isocalendar()
        prev_key = get_week_key(prev_iso.year, prev_iso.week)

        shift = ""
        week_data = self.load_all().get("weeks", {}).get(prev_key, {})
        if isinstance(week_data, dict):
            cells = week_data.get("cells", {})
            if isinstance(cells, dict):
                doctor_data = cells.get(doctor, {})
                if isinstance(doctor_data, dict):
                    sunday_payload = doctor_data.get("Dom")
                    if isinstance(sunday_payload, dict):
                        raw_shift = str(sunday_payload.get("shift", "")).strip()
                        shift = self._normalize_shift(raw_shift)

        self._prev_week_sunday_shift_cache[doctor] = shift
        return shift

    def _set_next_week_monday_shift_for_doctor(self, row: int, shift_value: str) -> bool:
        doctor = DOCTORS[row]
        current_monday = date.fromisocalendar(self.current_year, self.current_week_index, 1)
        next_monday = current_monday + timedelta(days=7)
        next_iso = next_monday.isocalendar()
        next_key = get_week_key(next_iso.year, next_iso.week)

        try:
            data = self.load_all()
            weeks = data.setdefault("weeks", {})
            week_data = weeks.setdefault(next_key, {})
            if not isinstance(week_data, dict):
                week_data = {}
                weeks[next_key] = week_data

            cells = week_data.setdefault("cells", {})
            if not isinstance(cells, dict):
                cells = {}
                week_data["cells"] = cells

            doctor_cells = cells.setdefault(doctor, {})
            if not isinstance(doctor_cells, dict):
                doctor_cells = {}
                cells[doctor] = doctor_cells

            monday_payload = doctor_cells.setdefault("Lun", {})
            if not isinstance(monday_payload, dict):
                monday_payload = {}
                doctor_cells["Lun"] = monday_payload

            monday_payload["shift"] = shift_value
            monday_payload["dest"] = ""
            monday_payload["flagged"] = False

            self.save_all(data)
            self._next_week_monday_shift_cache.pop(doctor, None)
            return True
        except OSError:
            self.statusBar().showMessage("Errore salvataggio assegnazione automatica", 3000)
            return False

    def _auto_assign_next_0_8(self, row: int, col: int) -> None:
        if col < len(DAYS) - 1:
            next_item = self.table.item(row, col + 1)
            if next_item and next_item.text() != "0-8":
                self.table.blockSignals(True)
                try:
                    next_item.setText("0-8")
                finally:
                    self.table.blockSignals(False)
            return

        if col == len(DAYS) - 1:
            self._set_next_week_monday_shift_for_doctor(row, "0-8")

    def segments_for_cell(self, text: str, col: int | None = None):
        segments = []
        errors: List[str] = []
        shift_line, dest_line = self._split_cell_lines(text)
        is_weekend = col in (6, 7)
        if not shift_line:
            return segments, errors, ""

        zero_label = normalize_zero_hour_label(shift_line)
        if zero_label:
            if dest_line:
                errors.append("Riga 2: deve essere vuota per questa etichetta")
            return segments, errors, zero_label

        special_label = normalize_special_hour_label(shift_line)
        if special_label:
            if dest_line:
                errors.append("Riga 2: deve essere vuota per questa etichetta")
            return segments, errors, special_label

        match = SHIFT_RE.match(shift_line)
        if not match:
            errors.append(f"Riga 1: formato turno non valido ({shift_line!r})")
            return segments, errors, ""
        shift = match.group(1).replace(" ", "")
        if shift not in SHIFT_HOURS:
            errors.append(f"Riga 1: turno non ammesso ({shift})")
            return segments, errors, ""

        if shift in {"20-24", "0-8"}:
            if dest_line:
                errors.append("Riga 2: deve essere vuota per il turno notturno")
            gn_segment = (20, 24, "GN") if shift == "20-24" else (0, 8, "GN")
            segments.append(gn_segment)
            return segments, errors, shift

        if shift in {"8-14", "8-15", "14-20", "8-16"}:
            if not dest_line:
                errors.append(DEST_REQUIRED_ERROR)
                return segments, errors, shift
            if "+" in dest_line:
                errors.append("Riga 2: turni di 6 ore non possono avere doppia destinazione")
                return segments, errors, shift
            normalized_dest = normalize_dest_label(dest_line)
            if not normalized_dest:
                errors.append(f"Riga 2: destinazione non ricosciuta ({dest_line!r})")
                return segments, errors, shift
            if shift == "8-14":
                segments.append((8, 14, normalized_dest))
            elif shift == "8-15":
                segments.append((8, 15, normalized_dest))
            elif shift == "14-20":
                segments.append((14, 20, normalized_dest))
            else:
                segments.append((8, 16, normalized_dest))
            return segments, errors, shift

        if shift == "8-20":
            if not dest_line and not is_weekend:
                errors.append(DEST_REQUIRED_ERROR)
                return segments, errors, shift
            if not dest_line and is_weekend:
                return segments, errors, shift
            if "+" in dest_line:
                parts = [part.strip() for part in dest_line.split("+")]
                if len(parts) != 2 or not all(parts):
                    errors.append("Riga 2: formato atteso 'A+B'")
                    return segments, errors, shift
                normalized_parts = [normalize_dest_label(part) for part in parts]
                if any(not part for part in normalized_parts):
                    errors.append(f"Riga 2: destinazione non ricosciuta ({dest_line!r})")
                    return segments, errors, shift
                segments.append((8, 14, normalized_parts[0]))
                segments.append((14, 20, normalized_parts[1]))
                return segments, errors, shift

            normalized_dest = normalize_dest_label(dest_line)
            if not normalized_dest:
                errors.append(f"Riga 2: destinazione non ricosciuta ({dest_line!r})")
                return segments, errors, shift
            segments.append((8, 14, normalized_dest))
            segments.append((14, 20, normalized_dest))
            return segments, errors, shift

        errors.append(f"Riga 1: turno non ammesso ({shift})")
        return segments, errors, shift

    def validate_cell_text(self, row: int, col: int, text: str) -> Tuple[float, List[str]]:
        """
        Ritorna:
        - ore calcolate dal turno in prima riga
        - lista di errori (turno/destinazione/notte)
        Regole:
        - riga 1: turno ammesso, opzionalmente con **
        - riga 2: destinazione validata in base al turno
        """
        total = 0.0
        segments, errors, shift = self.segments_for_cell(text, col)
        _ = segments
        if shift:
            total += SHIFT_HOURS.get(shift, 0)
            total += SPECIAL_HOUR_LABELS.get(shift, 0)

        if shift == "0-8":
            prev_shift = ""
            if col > 1:
                prev_item = self.table.item(row, col - 1)
                prev_text = prev_item.text() if prev_item else ""
                prev_shift, _ = self._split_cell_lines(prev_text)
                prev_shift = self._normalize_shift(prev_shift)
            elif col == 1:
                prev_shift = self._get_prev_week_sunday_shift_for_doctor(row)
            if prev_shift != "20-24":
                if col == 1:
                    errors.append("Notte incompleta: manca 20-24 la domenica della settimana precedente")
                else:
                    errors.append("Notte incompleta: manca 20-24 il giorno precedente")

        if shift == "20-24":
            next_shift = ""
            if col < len(DAYS) - 1:
                next_item = self.table.item(row, col + 1)
                next_text = next_item.text() if next_item else ""
                next_shift, _ = self._split_cell_lines(next_text)
                next_shift = self._normalize_shift(next_shift)
            elif col == len(DAYS) - 1:
                next_shift = self._get_next_week_monday_shift_for_doctor(row)
            if next_shift != "0-8":
                if col == len(DAYS) - 1:
                    errors.append("Notte incompleta: manca 0-8 il lunedÃ¬ della settimana successiva")
                else:
                    errors.append("Notte incompleta: manca 0-8 il giorno successivo")

        return total, errors

    def _get_line2_color(self, shift: str, dest: str, col: int) -> QColor | None:
        if shift in {"20-24", "0-8"}:
            return LINE2_YELLOW
        if shift == "8-20" and col in (6, 7):
            return LINE2_YELLOW
        color_key = dest.strip()
        if "+" in color_key:
            color_key = color_key.split("+", 1)[0].strip()
        return DEST_LINE2_COLORS.get(color_key.casefold())

    def _is_rs_shift(self, shift_line: str) -> bool:
        token = shift_line.strip()
        if token.endswith("**"):
            token = token[:-2].strip()
        return normalize_zero_hour_label(token) == "rs"

    def _is_zero_hour_shift(self, shift_line: str) -> bool:
        token = shift_line.strip()
        if token.endswith("**"):
            token = token[:-2].strip()
        return bool(normalize_zero_hour_label(token))

    def _is_special_hour_shift(self, shift_line: str) -> bool:
        token = shift_line.strip()
        if token.endswith("**"):
            token = token[:-2].strip()
        return bool(normalize_special_hour_label(token))

    def _get_cell_background(self, shift: str, dest: str, col: int) -> QColor | QBrush:
        line2_color = self._get_line2_color(shift, dest, col)
        if line2_color is not None:
            return line2_color
        if self._is_zero_hour_shift(shift) or self._is_special_hour_shift(shift):
            return ZERO_HOUR_STRIPE_BRUSH
        return WHITE_BG

    def _dest_has_guard_g(self, dest_line: str) -> bool:
        parts = [part.strip() for part in dest_line.split("+")]
        for part in parts:
            if normalize_dest_label(part) == "G":
                return True
        return False

    def _night_counts_from_cells(self, cells: dict) -> dict[str, int]:
        counts = {doctor: 0 for doctor in DOCTORS}
        for doctor, day_map in cells.items():
            if doctor not in counts or not isinstance(day_map, dict):
                continue
            doctor_count = 0
            for day in DAYS[1:]:
                payload = day_map.get(day)
                if isinstance(payload, dict):
                    shift = str(payload.get("shift", "")).strip()
                else:
                    shift = ""
                if self._normalize_shift(shift) == "20-24":
                    doctor_count += 1
            counts[doctor] = doctor_count
        return counts

    def _shift_hours_from_shift_line(self, shift_line: str) -> int:
        token = shift_line.strip()
        if token.endswith("**"):
            token = token[:-2].strip()
        normalized_shift = self._normalize_shift(token)
        if normalized_shift:
            return int(SHIFT_HOURS.get(normalized_shift, 0))
        normalized_special = normalize_special_hour_label(token)
        if normalized_special:
            return int(SPECIAL_HOUR_LABELS.get(normalized_special, 0))
        return 0

    def _flagged_hours_from_cells(self, cells: dict) -> dict[str, int]:
        totals = {doctor: 0 for doctor in DOCTORS}
        for doctor, day_map in cells.items():
            if doctor not in totals or not isinstance(day_map, dict):
                continue
            doctor_total = 0
            for day in DAYS[1:]:
                payload = day_map.get(day)
                if not isinstance(payload, dict):
                    continue
                shift = str(payload.get("shift", "")).strip()
                flagged = bool(payload.get("flagged", False) or ("**" in shift))
                if not flagged:
                    continue
                doctor_total += self._shift_hours_from_shift_line(shift)
            totals[doctor] = doctor_total
        return totals

    def _compute_year_night_totals(self, year: int) -> dict[str, int]:
        totals = {doctor: 0 for doctor in DOCTORS}
        start_of_year = date(year, 1, 1)

        all_data = self.load_all()
        weeks = all_data.get("weeks", {})
        if not isinstance(weeks, dict):
            return totals

        current_key = get_week_key(self.current_year, self.current_week_index)
        current_payload = self.serialize_week()
        current_seen = False

        for week_key, week_data in weeks.items():
            payload = current_payload if week_key == current_key else week_data
            if week_key == current_key:
                current_seen = True
            if not isinstance(payload, dict):
                continue
            cells = payload.get("cells", {})
            if not isinstance(cells, dict):
                continue

            m = re.match(r"^(\d{4})-W(\d{2})$", week_key)
            if not m:
                continue
            week_year = int(m.group(1))
            week_index = int(m.group(2))
            try:
                week_dates = get_week_dates_iso(week_year, week_index)
            except ValueError:
                continue

            for doctor in DOCTORS:
                day_map = cells.get(doctor, {})
                if not isinstance(day_map, dict):
                    continue
                for day_name, day_date in zip(DAYS[1:], week_dates):
                    if day_date < start_of_year or day_date.year != year:
                        continue
                    payload_day = day_map.get(day_name)
                    if not isinstance(payload_day, dict):
                        continue
                    shift = str(payload_day.get("shift", "")).strip()
                    if self._normalize_shift(shift) == "20-24":
                        totals[doctor] += 1

        if not current_seen:
            m = re.match(r"^(\d{4})-W(\d{2})$", current_key)
            if m:
                week_year = int(m.group(1))
                week_index = int(m.group(2))
                try:
                    week_dates = get_week_dates_iso(week_year, week_index)
                except ValueError:
                    week_dates = []
                cells = current_payload.get("cells", {})
                if isinstance(cells, dict) and week_dates:
                    for doctor in DOCTORS:
                        day_map = cells.get(doctor, {})
                        if not isinstance(day_map, dict):
                            continue
                        for day_name, day_date in zip(DAYS[1:], week_dates):
                            if day_date < start_of_year or day_date.year != year:
                                continue
                            payload_day = day_map.get(day_name)
                            if not isinstance(payload_day, dict):
                                continue
                            shift = str(payload_day.get("shift", "")).strip()
                            if self._normalize_shift(shift) == "20-24":
                                totals[doctor] += 1
        return totals

    def _compute_year_weekend_worked_totals(self, year: int) -> dict[str, int]:
        totals = {doctor: 0 for doctor in DOCTORS}
        all_data = self.load_all()
        weeks = all_data.get("weeks", {})
        if not isinstance(weeks, dict):
            return totals

        current_key = get_week_key(self.current_year, self.current_week_index)
        current_payload = self.serialize_week()
        current_seen = False

        def normalized_shift_token(day_payload) -> str:
            if isinstance(day_payload, dict):
                raw = str(day_payload.get("shift", "")).strip()
            elif isinstance(day_payload, str):
                raw = day_payload.strip()
            else:
                raw = ""
            if not raw:
                return ""
            token = raw.splitlines()[0].strip()
            if token.endswith("**"):
                token = token[:-2].strip()
            return token.casefold()

        def add_from_week_payload(week_key: str, payload: dict) -> None:
            m = re.match(r"^(\d{4})-W(\d{2})$", week_key)
            if not m:
                return
            week_year = int(m.group(1))
            week_index = int(m.group(2))
            try:
                week_dates = get_week_dates_iso(week_year, week_index)
            except ValueError:
                return
            # Considera weekend solo se sabato e domenica appartengono all'anno target.
            sat_date, sun_date = week_dates[5], week_dates[6]
            if sat_date.year != year or sun_date.year != year:
                return

            cells = payload.get("cells", {})
            if not isinstance(cells, dict):
                return

            for doctor in DOCTORS:
                day_map = cells.get(doctor, {})
                if not isinstance(day_map, dict):
                    continue
                sat_payload = day_map.get("Sab")
                sun_payload = day_map.get("Dom")
                sat_token = normalized_shift_token(sat_payload)
                sun_token = normalized_shift_token(sun_payload)
                sat_is_rs = sat_token == "rs"
                sun_is_rs = sun_token == "rs"
                has_any_weekend_shift = bool(sat_token or sun_token)
                if has_any_weekend_shift and not (sat_is_rs and sun_is_rs):
                    totals[doctor] += 1

        for week_key, week_data in weeks.items():
            payload = current_payload if week_key == current_key else week_data
            if week_key == current_key:
                current_seen = True
            if not isinstance(payload, dict):
                continue
            add_from_week_payload(week_key, payload)

        if not current_seen:
            add_from_week_payload(current_key, current_payload)

        return totals

    def _compute_year_flagged_hours_totals(self, year: int) -> dict[str, int]:
        totals = {doctor: 0 for doctor in DOCTORS}
        start_of_year = date(year, 1, 1)

        all_data = self.load_all()
        weeks = all_data.get("weeks", {})
        if not isinstance(weeks, dict):
            return totals

        current_key = get_week_key(self.current_year, self.current_week_index)
        current_payload = self.serialize_week()
        current_seen = False

        def add_from_week_payload(week_key: str, payload: dict) -> None:
            m = re.match(r"^(\d{4})-W(\d{2})$", week_key)
            if not m:
                return
            week_year = int(m.group(1))
            week_index = int(m.group(2))
            try:
                week_dates = get_week_dates_iso(week_year, week_index)
            except ValueError:
                return

            # Se disponibile usa il parziale settimanale salvato in JSON.
            flagged_hours = payload.get("flagged_hours")
            if isinstance(flagged_hours, dict):
                for doctor in DOCTORS:
                    value = flagged_hours.get(doctor, 0)
                    try:
                        totals[doctor] += int(value)
                    except (TypeError, ValueError):
                        pass
                return

            # Fallback retrocompatibile: ricava il parziale dalle celle.
            cells = payload.get("cells", {})
            if not isinstance(cells, dict):
                return
            for doctor in DOCTORS:
                day_map = cells.get(doctor, {})
                if not isinstance(day_map, dict):
                    continue
                for day_name, day_date in zip(DAYS[1:], week_dates):
                    if day_date < start_of_year or day_date.year != year:
                        continue
                    payload_day = day_map.get(day_name)
                    if not isinstance(payload_day, dict):
                        continue
                    shift = str(payload_day.get("shift", "")).strip()
                    flagged = bool(payload_day.get("flagged", False) or ("**" in shift))
                    if flagged:
                        totals[doctor] += self._shift_hours_from_shift_line(shift)

        for week_key, week_data in weeks.items():
            payload = current_payload if week_key == current_key else week_data
            if week_key == current_key:
                current_seen = True
            if not isinstance(payload, dict):
                continue
            add_from_week_payload(week_key, payload)

        if not current_seen:
            add_from_week_payload(current_key, current_payload)

        return totals

    def refresh_night_stats(self):
        target_year = self.current_year
        totals = self._compute_year_night_totals(target_year)
        weekend_totals = self._compute_year_weekend_worked_totals(target_year)
        flagged_totals = self._compute_year_flagged_hours_totals(target_year)
        self.stats_title.setText(f"Statistiche {target_year}")
        for row, doctor in enumerate(DOCTORS):
            nights_item = self.stats_table.item(row, 0)
            weekends_item = self.stats_table.item(row, 1)
            flagged_item = self.stats_table.item(row, 2)
            if nights_item:
                nights_item.setText(str(totals.get(doctor, 0)))
            if weekends_item:
                weekends_item.setText(str(weekend_totals.get(doctor, 0)))
            if flagged_item:
                flagged_item.setText(str(flagged_totals.get(doctor, 0)))
        for row in range(len(DOCTORS), self.stats_table.rowCount()):
            for col in range(self.stats_table.columnCount()):
                item = self.stats_table.item(row, col)
                if item:
                    item.setText("")
        self._fit_stats_panel_width()

    def _set_cell_style(
        self,
        row: int,
        col: int,
        bg: QColor | QBrush,
        tooltip: str,
        is_error: bool = False,
        dest_required_line2: bool = False,
    ):
        item = self.table.item(row, col)
        if not item:
            return
        item.setBackground(bg)
        item.setForeground(QColor(0, 0, 0))
        item.setToolTip(tooltip)
        item.setData(ERROR_CELL_ROLE, is_error)
        item.setData(DEST_REQUIRED_LINE2_ROLE, dest_required_line2)
        shift_line, _ = self._split_cell_lines(item.text() if item else "")
        item_font = item.font()
        item_font.setBold(shift_line.strip().endswith("**"))
        item.setFont(item_font)

    def _revalidate_non_analysis_rows(self) -> None:
        for row in range(len(DOCTORS), DOCTOR_ROWS_COUNT):
            hours = 0.0
            for col in range(1, len(DAYS)):
                item = self.table.item(row, col)
                text = item.text() if item else ""
                _, _, shift = self.segments_for_cell(text, col)
                _, dest_line = self._split_cell_lines(text)
                hours += SHIFT_HOURS.get(shift, 0)
                hours += SPECIAL_HOUR_LABELS.get(shift, 0)
                self._set_cell_style(row, col, self._get_cell_background(shift, dest_line, col), "")

            h_item = self.table.item(row, 0)
            if h_item:
                h_item.setBackground(WHITE_BG)
                h_item.setForeground(QColor(0, 0, 0))
                h_item.setText(str(int(hours)))
            header_item = self.table.verticalHeaderItem(row)
            if header_item:
                header_item.setBackground(HEADER_BLUE_BG)
                header_item.setForeground(HEADER_TEXT_FG)
                header_item.setToolTip("")

    def revalidate_week(self):
        self._is_loading = True
        self.table.blockSignals(True)
        try:
            self._next_week_monday_shift_cache.clear()
            self._prev_week_sunday_shift_cache.clear()
            day_segments = {col: {} for col in range(1, len(DAYS))}
            night_assignments = {col: {"20-24": [], "0-8": []} for col in range(1, len(DAYS))}
            rs_error_rows: set[int] = set()
            day_20_24_error_cols: set[int] = set()

            for row in range(len(DOCTORS)):
                hours = 0.0
                row_is_complete = True
                row_has_rs = False
                for col in range(1, len(DAYS)):
                    item = self.table.item(row, col)
                    text = item.text() if item else ""
                    shift_line, _ = self._split_cell_lines(text)
                    if not text.strip():
                        row_is_complete = False
                    if self._is_rs_shift(shift_line):
                        row_has_rs = True
                    segments, _, shift = self.segments_for_cell(text, col)
                    cell_hours, errors = self.validate_cell_text(row, col, text)
                    _, dest_line = self._split_cell_lines(text)
                    cell_bg = self._get_cell_background(shift, dest_line, col)
                    hours += cell_hours

                    if errors:
                        only_dest_required = all(err == DEST_REQUIRED_ERROR for err in errors)
                        if only_dest_required:
                            self._set_cell_style(
                                row,
                                col,
                                cell_bg,
                                "\n".join(errors),
                                is_error=True,
                                dest_required_line2=True,
                            )
                        else:
                            self._set_cell_style(row, col, PINK_BG, "\n".join(errors), is_error=True)
                    else:
                        self._set_cell_style(row, col, cell_bg, "")
                        if shift in {"20-24", "0-8"}:
                            night_assignments[col][shift].append(row)
                        for start, end, label in segments:
                            if label == "GN":
                                continue
                            key = (start, end, label)
                            day_segments[col].setdefault(key, []).append(row)

                h_item = self.table.item(row, 0)
                if h_item:
                    h_item.setBackground(WHITE_BG)
                    h_item.setForeground(QColor(0, 0, 0))
                    h_item.setText(str(int(hours)))

                header_item = self.table.verticalHeaderItem(row)
                if header_item:
                    if row_is_complete and not row_has_rs:
                        rs_error_rows.add(row)
                        header_item.setBackground(PINK_BG)
                        header_item.setForeground(QColor(0, 0, 0))
                        header_item.setToolTip("Errore: manca almeno un giorno RS nella settimana")
                    else:
                        header_item.setBackground(HEADER_BLUE_BG)
                        header_item.setForeground(HEADER_TEXT_FG)
                        header_item.setToolTip("")

            for col in range(1, len(DAYS)):
                col_is_complete = True
                col_has_20_24 = False
                col_count_8_20 = 0
                col_count_20_24 = 0
                col_has_guard_g = False
                for row in range(len(DOCTORS)):
                    item = self.table.item(row, col)
                    text = item.text().strip() if item else ""
                    if not text:
                        col_is_complete = False
                        continue
                    shift_line, dest_line = self._split_cell_lines(text)
                    normalized_shift = self._normalize_shift(shift_line)
                    if normalized_shift == "20-24":
                        col_has_20_24 = True
                        col_count_20_24 += 1
                    if normalized_shift == "8-20":
                        col_count_8_20 += 1
                    if normalized_shift == "14-20":
                        if self._dest_has_guard_g(dest_line):
                            col_has_guard_g = True
                    if normalized_shift == "8-20":
                        if self._dest_has_guard_g(dest_line):
                            col_has_guard_g = True

                day_header_item = self.table.horizontalHeaderItem(col)
                if not day_header_item:
                    continue
                header_tooltip = ""
                has_day_error = False
                if col_is_complete:
                    if col in (6, 7):
                        if col_count_8_20 != 1 or col_count_20_24 != 1:
                            has_day_error = True
                            header_tooltip = (
                                f"Errore {DAYS[col]}: colonna completa richiede esattamente "
                                f"1 turno 8-20 e 1 turno 20-24 "
                                f"(attuali: 8-20={col_count_8_20}, 20-24={col_count_20_24})"
                            )
                    else:
                        missing_rules = []
                        if not col_has_20_24:
                            missing_rules.append("almeno un turno 20-24")
                        if not col_has_guard_g:
                            missing_rules.append("almeno una guardia G in fascia 14-20 o turno 8-20")
                        if missing_rules:
                            has_day_error = True
                            header_tooltip = (
                                "Errore: colonna completa senza "
                                + " e ".join(missing_rules)
                            )

                if has_day_error:
                    day_20_24_error_cols.add(col)
                    day_header_item.setBackground(PINK_BG)
                    day_header_item.setForeground(QColor(0, 0, 0))
                    day_header_item.setToolTip(header_tooltip)
                else:
                    day_header_item.setBackground(HEADER_BLUE_BG)
                    day_header_item.setForeground(HEADER_TEXT_FG)
                    day_header_item.setToolTip("")

            for col in range(1, len(DAYS)):
                for (start, end, label), rows in day_segments[col].items():
                    if len(rows) <= 1:
                        continue
                    for row in rows:
                        item = self.table.item(row, col)
                        if not item or item.background().color() == PINK_BG:
                            continue
                        others = [DOCTORS[r] for r in rows if r != row]
                        other_name = ", ".join(others)
                        tooltip = f"Conflitto: {label} giÃ  assegnata a {other_name} ({start}-{end})"
                        self._set_cell_style(row, col, PINK_BG, tooltip, is_error=True)

                for night_shift in ("20-24", "0-8"):
                    rows = night_assignments[col][night_shift]
                    if len(rows) <= 1:
                        continue
                    for row in rows:
                        item = self.table.item(row, col)
                        if not item or item.background().color() == PINK_BG:
                            continue
                        others = [DOCTORS[r] for r in rows if r != row]
                        other_name = ", ".join(others)
                        tooltip = f"Conflitto: turno {night_shift} giÃ  assegnato a {other_name}"
                        self._set_cell_style(row, col, PINK_BG, tooltip, is_error=True)
            self._revalidate_non_analysis_rows()
            self.doctor_header.set_error_rows(rs_error_rows)
            self.day_header.set_error_cols(day_20_24_error_cols)
        finally:
            self.table.blockSignals(False)
            self._is_loading = False

    # ----------------------------
    # Persistenza JSON
    # ----------------------------

    def _default_all_data(self) -> dict:
        return {"version": 2, "doctors": DOCTORS, "weeks": {}}

    def _startup_week_from_data(self, fallback_year: int, fallback_week: int) -> Tuple[int, int]:
        all_data = self.load_all()
        weeks = all_data.get("weeks", {})
        if not isinstance(weeks, dict) or not weeks:
            return fallback_year, fallback_week

        last_selected_week = str(all_data.get("last_selected_week", "")).strip()
        parsed_last = parse_week_key(last_selected_week) if last_selected_week else None
        if parsed_last is not None and last_selected_week in weeks:
            return parsed_last

        best_key = ""
        best_parsed: Tuple[int, int] | None = None
        best_filled = -1
        latest_parsed: Tuple[int, int] | None = None
        for week_key, payload in weeks.items():
            week_key = str(week_key)
            parsed = parse_week_key(week_key)
            if parsed is None:
                continue
            if latest_parsed is None or parsed > latest_parsed:
                latest_parsed = parsed

            filled = count_filled_cells_in_week_payload(payload)
            if (
                filled > best_filled
                or (filled == best_filled and best_parsed is not None and parsed > best_parsed)
                or (filled == best_filled and best_parsed is None)
            ):
                best_filled = filled
                best_key = week_key
                best_parsed = parsed

        if best_parsed is not None and best_filled > 0:
            return best_parsed
        if latest_parsed is not None:
            return latest_parsed
        if parsed_last is not None:
            return parsed_last
        if best_parsed is None:
            return fallback_year, fallback_week
        return best_parsed

    def serialize_week(self) -> dict:
        cells = {}
        extra_rows = {}
        day_names = DAYS[1:]

        for row, doctor in enumerate(TABLE_DOCTORS):
            doctor_cells = {}
            for col, day in enumerate(day_names, start=1):
                item = self.table.item(row, col)
                text = item.text() if item else ""
                shift, dest = self._split_cell_lines(text)
                doctor_cells[day] = {
                    "shift": shift,
                    "dest": dest,
                    "flagged": "**" in shift,
                }
            cells[doctor] = doctor_cells

        for offset, row_name in enumerate(EXTRA_ROWS):
            row = EXTRA_START_ROW + offset
            row_cells = {}
            for col, day in enumerate(day_names, start=1):
                item = self.table.item(row, col)
                row_cells[day] = item.text() if item else ""
            extra_rows[row_name] = row_cells

        night_counts = self._night_counts_from_cells(cells)
        flagged_hours = self._flagged_hours_from_cells(cells)
        return {
            "cells": cells,
            "extra_rows": extra_rows,
            "night_counts": night_counts,
            "flagged_hours": flagged_hours,
        }

    def load_week(self, week_dict: dict) -> None:
        if not isinstance(week_dict, dict):
            self._clear_week_cells()
            return

        cells = week_dict.get("cells")
        if not isinstance(cells, dict):
            self._clear_week_cells()
            return

        self._clear_week_cells()
        doctor_to_row = {doctor: row for row, doctor in enumerate(TABLE_DOCTORS)}
        extra_to_row = {row_name: EXTRA_START_ROW + i for i, row_name in enumerate(EXTRA_ROWS)}
        day_to_col = {day: col for col, day in enumerate(DAYS[1:], start=1)}

        self._is_loading = True
        self.table.blockSignals(True)
        try:
            for doctor, day_data in cells.items():
                row = doctor_to_row.get(doctor)
                if row is None or not isinstance(day_data, dict):
                    continue
                for day, payload in day_data.items():
                    col = day_to_col.get(day)
                    if col is None or not isinstance(payload, dict):
                        continue
                    shift = str(payload.get("shift", "")).strip()
                    dest = str(payload.get("dest", "")).strip()
                    flagged = bool(payload.get("flagged", False))
                    if flagged and shift and "**" not in shift:
                        shift = f"{shift}**"

                    text = shift if not dest else f"{shift}\n{dest}"
                    item = self.table.item(row, col)
                    if item:
                        item.setText(text)

            extra_rows = week_dict.get("extra_rows", {})
            if isinstance(extra_rows, dict):
                for row_name, day_data in extra_rows.items():
                    row = extra_to_row.get(row_name)
                    if row is None or not isinstance(day_data, dict):
                        continue
                    for day, payload in day_data.items():
                        col = day_to_col.get(day)
                        if col is None:
                            continue
                        item = self.table.item(row, col)
                        if not item:
                            continue
                        if isinstance(payload, dict):
                            shift = str(payload.get("shift", "")).strip()
                            dest = str(payload.get("dest", "")).strip()
                            text = shift if not dest else f"{shift}\n{dest}"
                        else:
                            text = str(payload) if payload is not None else ""
                        item.setText(text)
        finally:
            self.table.blockSignals(False)
            self._is_loading = False

        self.revalidate_week()
        self._dirty = False

    def save_all(self, data: dict) -> None:
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        self.data_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_all(self) -> dict:
        if not self.data_file.exists():
            return self._default_all_data()

        try:
            raw = self.data_file.read_text(encoding="utf-8-sig")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError):
            return self._default_all_data()

        if not isinstance(data, dict):
            return self._default_all_data()

        version = data.get("version")
        if version == 2 and isinstance(data.get("weeks"), dict):
            data["doctors"] = DOCTORS
            return data

        if version == 1 and isinstance(data.get("cells"), dict):
            current_iso = date.today().isocalendar()
            week_key = get_week_key(current_iso.year, current_iso.week)
            migrated = self._default_all_data()
            migrated["weeks"][week_key] = {"cells": data.get("cells", {})}
            try:
                self.save_all(migrated)
            except OSError:
                pass
            return migrated

        return self._default_all_data()

    def save_current_week(self, show_message: bool = True) -> bool:
        week_key = get_week_key(self.current_year, self.current_week_index)
        try:
            data = self.load_all()
            weeks = data.setdefault("weeks", {})
            week_payload = self.serialize_week()
            weeks[week_key] = week_payload
            data["last_selected_week"] = week_key

            # Autofill cross-settimana: Dom 20-24 -> Lun 0-8 nella settimana successiva.
            current_monday = date.fromisocalendar(self.current_year, self.current_week_index, 1)
            next_monday = current_monday + timedelta(days=7)
            next_iso = next_monday.isocalendar()
            next_key = get_week_key(next_iso.year, next_iso.week)

            next_week_data = weeks.setdefault(next_key, {})
            if not isinstance(next_week_data, dict):
                next_week_data = {}
                weeks[next_key] = next_week_data
            next_cells = next_week_data.setdefault("cells", {})
            if not isinstance(next_cells, dict):
                next_cells = {}
                next_week_data["cells"] = next_cells

            current_cells = week_payload.get("cells", {})
            if isinstance(current_cells, dict):
                for doctor, day_map in current_cells.items():
                    if doctor not in DOCTORS:
                        continue
                    if not isinstance(day_map, dict):
                        continue
                    sunday_payload = day_map.get("Dom")
                    if not isinstance(sunday_payload, dict):
                        continue
                    sunday_shift = self._normalize_shift(str(sunday_payload.get("shift", "")).strip())
                    if sunday_shift != "20-24":
                        continue

                    doctor_cells = next_cells.setdefault(doctor, {})
                    if not isinstance(doctor_cells, dict):
                        doctor_cells = {}
                        next_cells[doctor] = doctor_cells
                    monday_payload = doctor_cells.setdefault("Lun", {})
                    if not isinstance(monday_payload, dict):
                        monday_payload = {}
                        doctor_cells["Lun"] = monday_payload
                    monday_payload["shift"] = "0-8"
                    monday_payload["dest"] = ""
                    monday_payload["flagged"] = False

            self.save_all(data)
        except OSError:
            self.statusBar().showMessage("Errore salvataggio", 2000)
            return False

        self._dirty = False
        if show_message:
            self.statusBar().showMessage(f"Salvato {week_key}", 2000)
        return True

    def schedule_autosave(self):
        if self._is_loading:
            return
        self._dirty = True
        self.autosave_timer.start()

    def closeEvent(self, event: QCloseEvent):
        self.autosave_timer.stop()
        self.save_current_week(show_message=False)
        self._save_window_size()
        super().closeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)

    # ----------------------------
    # Eventi
    # ----------------------------

    def on_text_live_changed(self, row: int, col: int, text: str):
        _ = (row, col, text)
        # Non revalidare durante la digitazione: interferisce con l'editor attivo.
        # La validazione completa viene applicata al commit della cella.
        return

    def on_item_committed(self, item: QTableWidgetItem):
        # evita loop su colonna h
        if item.column() == 0 or self._is_loading:
            return

        current_text = item.text() or ""
        shift_line, dest_line = self._split_cell_lines(current_text)
        normalized_shift = autocomplete_shift_line(shift_line).upper()
        normalized_dest = autocomplete_dest_line(dest_line)
        normalized_text = normalized_shift if not normalized_dest else f"{normalized_shift}\n{normalized_dest}"
        if normalized_text != item.text():
            self.table.blockSignals(True)
            try:
                item.setText(normalized_text)
            finally:
                self.table.blockSignals(False)

        if item.row() < len(DOCTORS):
            shift_line, _ = self._split_cell_lines(item.text() if item else "")
            if self._normalize_shift(shift_line) == "20-24":
                self._auto_assign_next_0_8(item.row(), item.column())
            self.revalidate_week()
            self.refresh_night_stats()
        elif item.row() < DOCTOR_ROWS_COUNT:
            self.revalidate_week()
        self.schedule_autosave()

    def on_max_lines_reached(self):
        self.statusBar().showMessage("Max 2 righe per cella", 2000)

    def _restore_window_size(self) -> None:
        settings = QSettings(APP_SETTINGS_ORG, APP_SETTINGS_APP)
        width = settings.value("window/width", 0, int)
        height = settings.value("window/height", 0, int)
        if width > 0 and height > 0:
            self.resize(width, height)
        self._restored_prev_visible = bool(settings.value("layout/prev_visible", False, bool))
        self._restored_stats_visible = bool(settings.value("layout/stats_visible", False, bool))
        self._prev_panel_last_width = settings.value("layout/prev_last_width", 0, int)
        self._stats_panel_last_width = settings.value("layout/stats_last_width", 0, int)
        raw_sizes = settings.value("layout/splitter_sizes", "", str) or ""
        restored_sizes: List[int] = []
        if raw_sizes:
            try:
                parsed = json.loads(raw_sizes)
                if isinstance(parsed, list):
                    restored_sizes = [max(0, int(v)) for v in parsed[:3]]
            except (TypeError, ValueError, json.JSONDecodeError):
                restored_sizes = []
        self._restored_splitter_sizes = restored_sizes

    def _save_window_size(self) -> None:
        settings = QSettings(APP_SETTINGS_ORG, APP_SETTINGS_APP)
        settings.setValue("window/width", self.width())
        settings.setValue("window/height", self.height())
        settings.setValue("layout/prev_visible", self.prev_panel.isVisible())
        settings.setValue("layout/stats_visible", self.stats_panel.isVisible())
        sizes = self._current_splitter_sizes()
        prev_size = sizes[0] if self.prev_panel.isVisible() else self._prev_panel_last_width
        stats_size = sizes[2] if self.stats_panel.isVisible() else self._stats_panel_last_width
        settings.setValue("layout/prev_last_width", int(max(0, prev_size)))
        settings.setValue("layout/stats_last_width", int(max(0, stats_size)))
        settings.setValue("layout/splitter_sizes", json.dumps(sizes))


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

