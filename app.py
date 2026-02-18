import sys
import re
import json
from pathlib import Path
from datetime import date, timedelta
from typing import List, Tuple

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QPalette, QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QPlainTextEdit,
    QStyledItemDelegate,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
)

# ----------------------------
# Config dati
# ----------------------------

DAYS = ["h", "Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]

DOCTORS = [
    "Aru", "Cabianca", "Casula", "Corda", "Del Rio", "Desogus", "Masillo",
    "Mattana", "Pili", "Piras D", "Piras F", "Pistincu", "Pitzalis",
    "Puddu", "Sanna", "Tolu"
]

# Turni ammessi e durata in ore
SHIFT_HOURS = {
    "8-14": 6,
    "14-20": 6,
    "8-20": 12,
    "20-24": 4,
    "0-8": 8,
    "8-16": 8,
}
DEST_LABELS = {
    "Orto",
    "Vasc",
    "Calo",
    "Zorcolo",
    "Pisanu",
    "SG",
    "G",
    "End",
    "Gpre",
    "DS",
    "ORL",
    "Opoli",
}  # TODO: incollare lista reale
PINK_BG = QColor(255, 220, 220)
ORANGE_BG = QColor(255, 235, 180)
WHITE_BG = QColor(255, 255, 255)

# accetta: "8-14", "8 - 14", "8-14**", "8-14 **"
SHIFT_RE = re.compile(r"^\s*(\d{1,2}\s*-\s*\d{1,2})\s*(\*\*)?\s*$")
DATA_FILE = Path(__file__).resolve().parent / "planner_data.json"


def get_max_iso_weeks(year: int) -> int:
    return date(year, 12, 28).isocalendar().week


def get_week_key(year: int, week_index: int) -> str:
    return f"{year}-W{week_index:02d}"


def get_week_dates_iso(year: int, week_index: int) -> List[date]:
    monday = date.fromisocalendar(year, week_index, 1)
    return [monday + timedelta(days=offset) for offset in range(7)]


# ----------------------------
# Delegate multilinea con evento live
# ----------------------------

class TwoLineEdit(QPlainTextEdit):
    max_lines_reached = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        palette = self.palette()
        palette.setColor(QPalette.Base, QColor(255, 255, 255))
        palette.setColor(QPalette.Text, QColor(0, 0, 0))
        self.setPalette(palette)

    def _line_count_after_insert(self, inserted_text: str) -> int:
        cursor = self.textCursor()
        current_text = self.toPlainText()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        next_text = current_text[:start] + inserted_text + current_text[end:]
        normalized = next_text.replace("\r\n", "\n").replace("\r", "\n")
        return normalized.count("\n") + 1

    def _reject_third_line(self):
        QApplication.beep()
        self.max_lines_reached.emit()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self._line_count_after_insert("\n") > 2:
                self._reject_third_line()
                return
        super().keyPressEvent(event)

    def insertFromMimeData(self, source):
        text = source.text()
        if text and self._line_count_after_insert(text) > 2:
            self._reject_third_line()
            return
        super().insertFromMimeData(source)


class MultilineDelegate(QStyledItemDelegate):
    text_live_changed = Signal(int, int, str)  # row, col, text
    max_lines_reached = Signal()

    def createEditor(self, parent, option, index):
        editor = TwoLineEdit(parent)
        editor.setTabChangesFocus(True)  # TAB cambia cella
        editor.textChanged.connect(lambda: self._on_text_changed(index, editor))
        editor.max_lines_reached.connect(self.max_lines_reached.emit)
        return editor

    def setEditorData(self, editor, index):
        editor.setPlainText(index.data() or "")

    def setModelData(self, editor, model, index):
        model.setData(index, editor.toPlainText())

    def _on_text_changed(self, index, editor):
        self.text_live_changed.emit(index.row(), index.column(), editor.toPlainText())


# ----------------------------
# Main window
# ----------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Planner Turni Medici")
        self.resize(1100, 650)
        self._is_loading = False
        self._dirty = False

        today = date.today()
        iso_today = today.isocalendar()
        self.current_year = iso_today.year
        self.current_week_index = iso_today.week

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
        controls.addStretch()
        layout.addLayout(controls)

        self.table = QTableWidget()
        layout.addWidget(self.table)
        self.statusBar()
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.setInterval(1000)
        self.autosave_timer.timeout.connect(self.save_current_week)

        self._setup_table()
        self.year_spin.valueChanged.connect(self.on_week_selector_changed)
        self.week_spin.valueChanged.connect(self.on_week_selector_changed)
        self._load_selected_week(initial=True)

    def _setup_table(self):
        self.table.setRowCount(len(DOCTORS))
        self.table.setColumnCount(len(DAYS))

        self.table.setHorizontalHeaderLabels(DAYS)
        self.table.setVerticalHeaderLabels(DOCTORS)

        # Editing stile Excel
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        two_lines_height = self.table.fontMetrics().lineSpacing() * 2 + 6
        self.table.verticalHeader().setDefaultSectionSize(two_lines_height)

        # Crea celle
        for r in range(len(DOCTORS)):
            for c in range(len(DAYS)):
                item = QTableWidgetItem("")
                item.setTextAlignment(Qt.AlignTop | Qt.AlignLeft)
                item.setBackground(QColor(255, 255, 255))
                item.setForeground(QColor(0, 0, 0))

                # Colonna h: read-only e centrata
                if c == 0:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    item.setTextAlignment(Qt.AlignCenter)

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

    def _set_week_headers(self, week_dates: List[date]):
        headers = ["h"] + [f"{day}\n{dt.strftime('%d/%m')}" for day, dt in zip(DAYS[1:], week_dates)]
        self.table.setHorizontalHeaderLabels(headers)
        self.week_range_label.setText(f"{week_dates[0].strftime('%d/%m')}–{week_dates[-1].strftime('%d/%m')}")

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
            for row in range(len(DOCTORS)):
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

        all_data = self.load_all()
        new_key = get_week_key(year, week_index)
        week_data = all_data.get("weeks", {}).get(new_key)

        if isinstance(week_data, dict):
            self.load_week(week_data)
            self.statusBar().showMessage(f"Caricato {new_key}", 2000)
        else:
            self._clear_week_cells()
            self._dirty = False
            self.statusBar().showMessage("Nuova settimana (vuota)", 2000)

        self.current_year = year
        self.current_week_index = week_index
        if not initial and old_key != new_key:
            self.autosave_timer.stop()

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

    def segments_for_cell(self, text: str):
        segments = []
        errors: List[str] = []
        shift_line, dest_line = self._split_cell_lines(text)
        if not shift_line:
            return segments, errors, ""

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

        if shift in {"8-14", "14-20", "8-16"}:
            if not dest_line:
                errors.append("Riga 2: destinazione obbligatoria")
                return segments, errors, shift
            if "+" in dest_line:
                errors.append("Riga 2: non usare '+' per questo turno")
                return segments, errors, shift
            if dest_line not in DEST_LABELS:
                errors.append(f"Riga 2: destinazione non valida ({dest_line!r})")
                return segments, errors, shift
            if shift == "8-14":
                segments.append((8, 14, dest_line))
            elif shift == "14-20":
                segments.append((14, 20, dest_line))
            else:
                segments.append((8, 16, dest_line))
            return segments, errors, shift

        if shift == "8-20":
            if not dest_line:
                errors.append("Riga 2: destinazione obbligatoria")
                return segments, errors, shift
            if "+" in dest_line:
                parts = [part.strip() for part in dest_line.split("+")]
                if len(parts) != 2 or not all(parts):
                    errors.append("Riga 2: formato atteso 'A+B'")
                    return segments, errors, shift
                if any(part not in DEST_LABELS for part in parts):
                    errors.append(f"Riga 2: destinazione non valida ({dest_line!r})")
                    return segments, errors, shift
                segments.append((8, 14, parts[0]))
                segments.append((14, 20, parts[1]))
                return segments, errors, shift

            if dest_line not in DEST_LABELS:
                errors.append(f"Riga 2: destinazione non valida ({dest_line!r})")
                return segments, errors, shift
            segments.append((8, 14, dest_line))
            segments.append((14, 20, dest_line))
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
        segments, errors, shift = self.segments_for_cell(text)
        _ = segments
        if shift:
            total += SHIFT_HOURS.get(shift, 0)

        if shift == "0-8":
            prev_shift = ""
            if col > 1:
                prev_item = self.table.item(row, col - 1)
                prev_text = prev_item.text() if prev_item else ""
                prev_shift, _ = self._split_cell_lines(prev_text)
                prev_shift = self._normalize_shift(prev_shift)
            if prev_shift != "20-24":
                errors.append("Notte incompleta: manca 20-24 il giorno precedente")

        if shift == "20-24":
            next_shift = ""
            if col < len(DAYS) - 1:
                next_item = self.table.item(row, col + 1)
                next_text = next_item.text() if next_item else ""
                next_shift, _ = self._split_cell_lines(next_text)
                next_shift = self._normalize_shift(next_shift)
            if next_shift != "0-8":
                errors.append("Notte incompleta: manca 0-8 il giorno successivo")

        return total, errors

    def _set_cell_style(self, row: int, col: int, bg: QColor, tooltip: str):
        item = self.table.item(row, col)
        if not item:
            return
        item.setBackground(bg)
        item.setForeground(QColor(0, 0, 0))
        item.setToolTip(tooltip)

    def revalidate_week(self):
        self._is_loading = True
        self.table.blockSignals(True)
        try:
            day_segments = {col: {} for col in range(1, len(DAYS))}
            night_assignments = {col: {"20-24": [], "0-8": []} for col in range(1, len(DAYS))}

            for row in range(len(DOCTORS)):
                hours = 0.0
                for col in range(1, len(DAYS)):
                    item = self.table.item(row, col)
                    text = item.text() if item else ""
                    segments, _, shift = self.segments_for_cell(text)
                    cell_hours, errors = self.validate_cell_text(row, col, text)
                    hours += cell_hours

                    if errors:
                        self._set_cell_style(row, col, PINK_BG, "\n".join(errors))
                    else:
                        self._set_cell_style(row, col, WHITE_BG, "")
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
                    if abs(hours - round(hours)) < 1e-9:
                        h_item.setText(str(int(round(hours))))
                    else:
                        h_item.setText(f"{hours:.1f}")

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
                        tooltip = f"Conflitto: {label} già assegnata a {other_name} ({start}-{end})"
                        self._set_cell_style(row, col, ORANGE_BG, tooltip)

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
                        tooltip = f"Conflitto: turno {night_shift} già assegnato a {other_name}"
                        self._set_cell_style(row, col, ORANGE_BG, tooltip)
        finally:
            self.table.blockSignals(False)
            self._is_loading = False

    # ----------------------------
    # Persistenza JSON
    # ----------------------------

    def _default_all_data(self) -> dict:
        return {"version": 2, "doctors": DOCTORS, "weeks": {}}

    def serialize_week(self) -> dict:
        cells = {}
        day_names = DAYS[1:]

        for row, doctor in enumerate(DOCTORS):
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

        return {"cells": cells}

    def load_week(self, week_dict: dict) -> None:
        if not isinstance(week_dict, dict):
            self._clear_week_cells()
            return

        cells = week_dict.get("cells")
        if not isinstance(cells, dict):
            self._clear_week_cells()
            return

        self._clear_week_cells()
        doctor_to_row = {doctor: row for row, doctor in enumerate(DOCTORS)}
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
        finally:
            self.table.blockSignals(False)
            self._is_loading = False

        self.revalidate_week()
        self._dirty = False

    def save_all(self, data: dict) -> None:
        DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_all(self) -> dict:
        if not DATA_FILE.exists():
            return self._default_all_data()

        try:
            raw = DATA_FILE.read_text(encoding="utf-8")
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
            weeks[week_key] = self.serialize_week()
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
        super().closeEvent(event)

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
        self.revalidate_week()
        self.schedule_autosave()

    def on_max_lines_reached(self):
        self.statusBar().showMessage("Max 2 righe per cella", 2000)


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
