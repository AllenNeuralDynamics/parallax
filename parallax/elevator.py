from zaber_motion import Library as ZaberLibrary
from zaber_motion.ascii import Connection as ZaberConnection
ZaberLibrary.enable_device_db_store() # initialize the zaber library

from serial.tools.list_ports import comports as list_comports


def list_elevators():
    elevators = []
    for comport in list_comports():
        if (comport.vid == ZaberXMCC2Elevator.VID):
            if (comport.pid == ZaberXMCC2Elevator.PID):
                elevators.append(ZaberXMCC2Elevator(comport))
    return elevators


class Elevator:

    """
    Elevator base class.
    An elevator is the device abstraction representing the heavy mechanics
    which lift the entire rig up and down.
    This base class defines a common interface for these systems.
    """

    def __init__(self):
        pass

    def get_position(self):
        raise NotImplementedError

    def move_relative(self, delta):
        raise NotImplementedError

    def move_absolute(self, pos):
        raise NotImplementedError
    
    def home(self):
        raise NotImplementedError
    
    def get_firmware_setpoint(self, number):
        raise NotImplementedError

    def set_firmware_setpoint(self, number, pos):
        raise NotImplementedError


class ZaberXMCC2Elevator(Elevator):

    VID = 10553
    PID = 18882

    def __init__(self, comport):
        """
        comport is a 'port' as returned by serial.tools.list_ports()
        """
        self.comport = comport

        self.conn = ZaberConnection.open_serial_port(self.comport.device)
        self.device = self.conn.detect_devices()[0]
        self.lockstep = self.device.get_lockstep(1)
        self.primary_axis = self.device.get_axis(self.lockstep.get_axis_numbers()[0])
        self.axis_settings = self.primary_axis.settings

        self._name = 'Zaber X-MCC2 Lockstep (%s)' % self.comport.device

        self.get_speed()

    @property
    def name(self):
        return self._name

    def get_position(self):
        return self.primary_axis.get_position()

    def move_relative(self, delta):
        delta *= (-1)   # zaber stages are inverted so up is down
        self.lockstep.move_relative(delta)

    def move_absolute(self, pos):
        self.lockstep.move_absolute(pos)

    def get_firmware_setpoint(self, number):
        resp = self.conn.generic_command('tools storepos %d' % number, device=1)
        return int(resp.data.split()[0])    # use first axis only

    def set_firmware_setpoint(self, number, pos):
        resp = self.conn.generic_command('tools storepos %d %d' % (number, pos),
                                            device=1)

    def get_speed(self):
        speed = self.axis_settings.get('maxspeed')
        return speed    # float

    def set_speed(self, speed):
        speed = axis_settings.get('maxspeed', speed)

