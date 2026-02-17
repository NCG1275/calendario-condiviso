import sys
import re
from typing import List, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QPlainTextEdit,
    QStyledItemDelegate,
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

# accetta: "8-14", "8 - 14", "8-14**", "8-14 **"
SHIFT_RE = re.compile(r"^\s*(\d{1,2}\s*-\s*\d{1,2})\s*(\*\*)?\s*$")


# ----------------------------
# Delegate multilinea con evento live
# ----------------------------

class MultilineDelegate(QStyledItemDelegate):
    text_live_changed = Signal(int, int, str)  # row, col, text

    def createEditor(self, parent, option, index):
        editor = QPlainTextEdit(parent)
        editor.setTabChangesFocus(True)  # TAB cambia cella
        editor.textChanged.connect(lambda: self._on_text_changed(index, editor))
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

        self.table = QTableWidget()
        self.setCentralWidget(self.table)

        self._setup_table()

    def _setup_table(self):
        self.table.setRowCount(len(DOCTORS))
        self.table.setColumnCount(len(DAYS))

        self.table.setHorizontalHeaderLabels(DAYS)
        self.table.setVerticalHeaderLabels(DOCTORS)

        # Editing stile Excel
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.table.verticalHeader().setDefaultSectionSize(70)

        # Crea celle
        for r in range(len(DOCTORS)):
            for c in range(len(DAYS)):
                item = QTableWidgetItem("")
                item.setTextAlignment(Qt.AlignTop | Qt.AlignLeft)

                # Colonna h: read-only e centrata
                if c == 0:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    item.setTextAlignment(Qt.AlignCenter)

                self.table.setItem(r, c, item)

        # Delegate multilinea per tutte le colonne dei giorni (1..7)
        self.delegate = MultilineDelegate()
        self.delegate.text_live_changed.connect(self.on_text_live_changed)
        for c in range(1, len(DAYS)):
            self.table.setItemDelegateForColumn(c, self.delegate)

        # Quando una cella viene "committata" (finito l'editing)
        self.table.itemChanged.connect(self.on_item_committed)

        # Inizializza ore
        for r in range(len(DOCTORS)):
            self.update_hours_for_row(r)

    # ----------------------------
    # Parsing e validazione
    # ----------------------------

    def validate_cell_text(self, text: str) -> Tuple[float, List[str]]:
        """
        Ritorna:
        - ore totali calcolate dai turni riconosciuti
        - lista di errori (righe non valide)
        Regole:
        - righe vuote ignorate
        - ogni riga non vuota deve essere uno shift ammesso, opzionalmente con **
        """
        total = 0.0
        errors: List[str] = []

        for i, raw_line in enumerate(text.splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue

            m = SHIFT_RE.match(line)
            if not m:
                errors.append(f"Riga {i}: formato non valido ({raw_line!r})")
                continue

            shift = m.group(1).replace(" ", "")  # "8 - 14" -> "8-14"
            flagged = bool(m.group(2))  # ** presente? per ora non cambia le ore

            if shift not in SHIFT_HOURS:
                errors.append(f"Riga {i}: turno non ammesso ({shift})")
                continue

            total += SHIFT_HOURS[shift]

            # Se in futuro vuoi che ** abbia significato sulle ore o altro, è qui.
            _ = flagged  # placeholder per chiarezza

        return total, errors

    def apply_cell_style(self, row: int, col: int, errors: List[str]):
        """
        Se errors è vuota: stile normale.
        Se errors non è vuota: sfondo rosato + tooltip.
        """
        item = self.table.item(row, col)
        if not item:
            return

        if errors:
            item.setBackground(QColor(255, 220, 220))  # rosa chiaro
            item.setToolTip("\n".join(errors))
        else:
            item.setBackground(QColor(255, 255, 255))  # bianco
            item.setToolTip("")

    # ----------------------------
    # Calcolo ore settimanali
    # ----------------------------

    def update_hours_for_row(self, row: int):
        hours = 0.0
        # somma da colonna 1 a 7 (Lun..Dom)
        for c in range(1, len(DAYS)):
            item = self.table.item(row, c)
            if not item:
                continue
            cell_hours, errors = self.validate_cell_text(item.text())
            hours += cell_hours
            self.apply_cell_style(row, c, errors)

        h_item = self.table.item(row, 0)
        if h_item:
            # formato: intero se possibile, altrimenti 1 decimale
            if abs(hours - round(hours)) < 1e-9:
                h_item.setText(str(int(round(hours))))
            else:
                h_item.setText(f"{hours:.1f}")

    # ----------------------------
    # Eventi
    # ----------------------------

    def on_text_live_changed(self, row: int, col: int, text: str):
        # col 0 è "h"
        if col == 0:
            return
        # aggiornamento live della riga (ore + colori)
        self.update_hours_for_row(row)

    def on_item_committed(self, item: QTableWidgetItem):
        # evita loop su colonna h
        if item.column() == 0:
            return
        self.update_hours_for_row(item.row())


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()