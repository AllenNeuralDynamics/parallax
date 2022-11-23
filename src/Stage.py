#!/usr/bin/env python3

from newscale.multistage import USBXYZStage

class Stage():

    def __init__(self, ip=None, serial=None):

        if ip is not None:
            self.ip = ip
            self.name = ip
            self.device = PoEXYZStage(ip)
        elif serial is not None:
            self.serial = serial
            self.name = serial
            self.device = USBXYZStage(serial)

        self.initialize()

    def initialize(self):
        self.origin = [7500,7500,7500]

    def getName(self):
        return self.name

    def setOrigin(self, x, y, z):
        self.origin = [x,y,z]

    def getOrigin(self):
        return self.origin

    def getPosition(self, relative=False):
        pos = self.device.get_position('x', 'y', 'z')
        return pos['x'], pos['y'], pos['z']

    def moveToTarget_1d(self, axis, position, relative=False):
        self.device.move_absolute(x=x, y=y, z=z)

    def moveToTarget_3d(self, x, y, z, relative=False, safe=True):
        # TODO implement safe parameter
        if relative:
            xo,yo,zo = self.getOrigin()
            x += xo
            y += yo
            z += zo
        self.device.move_absolute(x=x, y=y, z=z)

    def moveDistance_1d(self, axis, distance):
        # TODO re-implement based on move_relative()
        x,y,z = self.getPosition()
        if axis == 'x':
            x += distance
        elif axis == 'y':
            y += distance
        elif axis == 'z':
            z += distance
        self.device.move_absolute(x=x, y=y, z=z)

    def moveDistance_3d(self, x, y, z):
        pass    # TODO, implement based on move_relative()

    def getSpeed(self):
        d = self.device.get_closed_loop_speed_and_accel('x')
        speed = d['x'][0]
        return speed

    def setSpeed(self, speed):
        accel = self.getAccel()
        self.device.set_closed_loop_speed_and_accel(global_setting=(speed, accel))

    def getAccel(self):
        d = self.device.get_closed_loop_speed_and_accel('x')
        accel = d['x'][1]
        return accel

    def halt(self):
        pass


if __name__ == '__main__':
    from random import uniform
    stage = Stage(serial='/dev/ttyUSB0')
    stage.moveToTarget_3d(x=uniform(0, 15000), y=uniform(0, 15000), z=uniform(0, 15000))
