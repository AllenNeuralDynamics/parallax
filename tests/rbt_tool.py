#!/usr/bin/env python -i
from PyQt5.QtWidgets import QApplication
from parallax.model import Model
from parallax.rigid_body_transform_tool import RigidBodyTransformTool
model = Model()
app = QApplication([])
rbt = RigidBodyTransformTool(model)
rbt.show()
app.exec()

