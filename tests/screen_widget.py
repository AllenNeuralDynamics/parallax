#!/usr/bin/env python -i
import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout
from parallax.screen_widget import ScreenWidget

if len(sys.argv) > 1:
    filename = sys.argv[1]
else:
    filename = None

app = QApplication([])
screen = ScreenWidget(filename=filename)
window = QWidget()
layout = QVBoxLayout()
layout.addWidget(screen)
window.setLayout(layout)
window.show()
app.exec()

