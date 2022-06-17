#!/usr/bin/python3

from MotorStatus import MotorStatus

import time

JOG_STEPS = 10000   # 5 mm
# steps are 0.5 um by default

class Stage():

    def __init__(self, sock):
        self.sock = sock
        self.status = None

    def close(self):
        self.sock.close()

    #################################

    """
    debug commands
    """

    def getIP(self):
        return self.sock.getpeername()[0]

    def getFirmwareVersion(self):
        cmd = b"TR<01>\r"
        self.sock.sendall(cmd)
        resp = self.sock.recv(1024).decode('utf-8').strip('<>\r')
        version = resp.split()[3]
        info = resp.split()[4]
        fw_version = '%s (%s)' % (version, info)
        return fw_version

    def getStatus(self):
        cmd = b"<10>\r"
        self.sock.sendall(cmd)
        resp = self.sock.recv(1024).decode('utf-8').strip('<>\r')
        status_bitfield = int(resp.split()[1], 16)
        position = int(resp.split()[2], 16)
        self.status = MotorStatus(status_bitfield, position)

    def getPosition(self):
        cmd = b"<10>\r"

        self.selectAxis('x')
        self.sock.sendall(cmd)
        time.sleep(0.1)
        resp = self.sock.recv(1024).decode('utf-8').strip('<>\r')
        print(resp)
        x = int(resp.split()[2], 16)

        self.selectAxis('y')
        self.sock.sendall(cmd)
        time.sleep(0.1)
        resp = self.sock.recv(1024).decode('utf-8').strip('<>\r')
        print(resp)
        y = int(resp.split()[2], 16)

        self.selectAxis('z')
        self.sock.sendall(cmd)
        time.sleep(0.1)
        resp = self.sock.recv(1024).decode('utf-8').strip('<>\r')
        print(resp)
        z = int(resp.split()[2], 16)

        return x, y, z

    #################################

    """
    setup commands
    """

    def initialize(self):
        self.calibrateFrequency()
        self.verifyTravel()

    def calibrateFrequency(self):
        cmd = b"<87 5>\r"
        self.sock.sendall(cmd)
        resp = self.sock.recv(1024)

    def verifyTravel(self):
        pass    # TODO

    def setDriveMode(self, mode):
        if mode == 'open':
            cmd = b"<20 0>\r"
        elif mode == 'closed':
            cmd = b"<20 1>\r"
        self.sock.sendall(cmd)
        resp = self.sock.recv(1024)

    def queryDriveMode(self):
        cmd = b"<20 R>\r"
        self.sock.sendall(cmd)
        resp = self.sock.recv(1024)

    def selectAxis(self, axis):
        if (axis=='x') or (axis=='X'):
            cmd = b"TR<A0 01>\r"
        elif (axis=='y') or (axis=='Y'):
            cmd = b"TR<A0 02>\r"
        elif (axis=='z') or (axis=='Z'):
            cmd = b"TR<A0 03>\r"
        else:
            print('Error: axis not recognized')
            return
        self.sock.sendall(cmd)
        resp = self.sock.recv(1024)

    def querySelectedAxis(self):
        cmd = b"TR<A0>\r"
        self.sock.sendall(cmd)
        resp = self.sock.recv(1024)

    #################################

    """
    per-axis motion commands
    """

    def runForward(self):
        cmd = b"<04 1>\r"
        self.sock.sendall(cmd)
        resp = self.sock.recv(1024)

    def runBackward(self):
        cmd = b"<04 0>\r"
        self.sock.sendall(cmd)
        resp = self.sock.recv(1024)

    def halt(self):
        cmd = b"<03>\r"
        resp = self.sock.recv(1024)
        # no response after halt command?

    def jogForward(self):
        cmd = "<06 1 {0:08x}>\r".format(JOG_STEPS)
        cmd_bytes = bytes(cmd, 'utf-8')
        self.sock.sendall(cmd_bytes)
        resp = self.sock.recv(1024)

    def jogBackward(self):
        cmd = "<06 0 {0:08x}>\r".format(JOG_STEPS)
        cmd_bytes = bytes(cmd, 'utf-8')
        self.sock.sendall(cmd_bytes)
        resp = self.sock.recv(1024)

    def moveToTarget(self, targetValue):
        targetValue = int(targetValue)
        cmd = "<08 {0:08x}>\r".format(targetValue)
        cmd_bytes = bytes(cmd, 'utf-8')
        self.sock.sendall(cmd_bytes)
        resp = self.sock.recv(1024)
    
    #################################

    """
    higher level motion commands
    """

    def moveToTarget_mm3d(self, x, y, z):
        self.selectAxis('x')
        self.moveToTarget(15000 + 15000*x/7.5)
        self.selectAxis('y')
        self.moveToTarget(15000 + 15000*y/7.5)
        self.selectAxis('z')
        self.moveToTarget(15000 + 15000*z/7.5)

    def center(self):
        self.moveToTarget_mm3d(0, 0, 0)


if __name__ == '__main__':

    import socket
    IP = '10.128.49.22'
    PORT = 23
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((IP, PORT))
    stage = Stage(sock)

    print('position: ', stage.getPosition())

    """
    stage.selectAxis('y')
    stage.setDriveMode('closed')
    stage.jogForward()
    """

    stage.close()

