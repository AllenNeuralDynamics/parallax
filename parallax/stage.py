# from newscale.multistage import USBXYZStage


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

    def get_name(self):
        return self.name

    def set_origin(self, x, y, z):
        self.origin = [x,y,z]

    def get_origin(self):
        return self.origin

    def get_position(self, relative=False):
        pos = self.device.get_position('x', 'y', 'z')
        return pos['x'], pos['y'], pos['z']

    def move_to_target_1d(self, axis, position, relative=False):
        self.device.move_absolute(x=x, y=y, z=z)

    def move_to_target_3d(self, x, y, z, relative=False, safe=True):
        # TODO implement safe parameter
        if relative:
            xo,yo,zo = self.get_origin()
            x += xo
            y += yo
            z += zo
        self.device.move_absolute(x=x, y=y, z=z)

    def move_distance_1d(self, axis, distance):
        # TODO re-implement based on move_relative()
        x,y,z = self.get_position()
        if axis == 'x':
            x += distance
        elif axis == 'y':
            y += distance
        elif axis == 'z':
            z += distance
        self.device.move_absolute(x=x, y=y, z=z)

    def move_distance_3d(self, x, y, z):
        pass    # TODO, implement based on move_relative()

    def get_speed(self):
        d = self.device.get_closed_loop_speed_and_accel('x')
        speed = d['x'][0]
        return speed

    def set_speed(self, speed):
        accel = self.get_accel()
        self.device.set_closed_loop_speed_and_accel(global_setting=(speed, accel))

    def get_accel(self):
        d = self.device.get_closed_loop_speed_and_accel('x')
        accel = d['x'][1]
        return accel

    def halt(self):
        pass
