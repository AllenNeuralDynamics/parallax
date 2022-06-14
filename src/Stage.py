class Stage():

    def __init__(self, sock):
        self.sock = sock
        pass

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


