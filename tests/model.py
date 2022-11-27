#!/usr/bin/env python -i
from parallax.model import Model

model = Model()
model.scan_for_cameras()
print('ncameras = ', model.ncameras)
model.clean()

