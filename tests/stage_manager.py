#!/usr/bin/env python -i
from PyQt5.QtWidgets import QApplication
from parallax.model import Model
from parallax.stage_manager import StageManager

model = Model()
app = QApplication([])
stage_manager = StageManager(model)
stage_manager.show()
app.exec()

