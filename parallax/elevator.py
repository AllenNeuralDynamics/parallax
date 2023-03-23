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
    

class ZaberXMCC2Elevator(Elevator):

    VID = 10553
    PID = 18882

    def __init__(self, comport):
        """
        comport is a 'port' as returned by serial.tools.list_ports()
        """
        self.comport = comport

        connection = ZaberConnection.open_serial_port(self.comport.device)
        self.device = connection.detect_devices()[0]
        self.lockstep = self.device.get_lockstep(1)
        self.primary_axis = self.device.get_axis(self.lockstep.get_axis_numbers()[0])

        self._name = 'Zaber X-MCC2 Lockstep (%s)' % self.comport.device

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

    def home(self):
        self.conn.get_axis(1).home()
    
