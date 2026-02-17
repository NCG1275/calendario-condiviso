import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QTableWidget, QTableWidgetItem)

DAYS = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
DOCTORS = ["Aru", "Cabianca", "Casula", "Corda", "Del Rio", "Desogus", "Masillo", "Mattana", "Pili", "Piras D.", "Piras F.", "Pistincu", "Pitzalis", "Puddu", "Sanna", "Tolu"]

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Planner Turni Medici")
        self.resize(900, 500)

        # crea la tabella
        table = QTableWidget()

        # dimensioni della griglia
        table.setRowCount(len(DOCTORS))
        table.setColumnCount(len(DAYS))

        # intestazioni
        table.setHorizontalHeaderLabels(DAYS)
        table.setVerticalHeaderLabels(DOCTORS)

        # riempiamo con celle vuote editabili
        for r in range(len(DOCTORS)):
            for c in range(len(DAYS)):
                item = QTableWidgetItem("")
                table.setItem(r, c, item)
        
        # metti la tabella al centro della finestra
        self.setCentralWidget(table)


app = QApplication(sys.argv)
window = MainWindow()
window.show()
sys.exit(app.exec())
