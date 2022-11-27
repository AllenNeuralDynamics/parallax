#!/usr/bin/env python -i

from PyQt5.QtWidgets import QApplication
from parallax.model import Model
from parallax.rigid_body_transform_tool import RigidBodyTransformTool

model = Model()
app = QApplication([])
dlg = RigidBodyTransformTool(model)
dlg.show()
app.exec()

