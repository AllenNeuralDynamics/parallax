from zaber_motion import Library as ZaberLibrary
from zaber_motion.ascii import Connection as ZaberConnection

from serial.tools.list_ports import comports as list_comports

# initialize the zaber library
ZaberLibrary.enable_device_db_store()


def list_zaber_stages():
    zabers = []
    for comport in list_comports():
        if comport.description == 'X-MCC2':
            zabers.append(ZaberStage(comport))
    return zabers


class ZaberStage:

    def __init__(self, comport):
        self.comport = comport
        self.conn = ZaberConnection.open_serial_port(comport.device)

    @property
    def name(self):
        return self.comport.device

    def home(self):
        self.conn.get_axis(1).home()
    
