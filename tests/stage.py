#!/usr/bin/env python -i
from random import uniform
from parallax.stage import Stage
stage = Stage(serial='/dev/ttyUSB0')
stage.move_to_target_3d(x=uniform(0, 15000), y=uniform(0, 15000), z=uniform(0, 15000))
