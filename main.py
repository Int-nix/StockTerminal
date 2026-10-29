import sys
from PySide6.QtWidgets import QApplication
from config import APP_NAME
from gui.window import StockTerminal


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    window = StockTerminal()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())