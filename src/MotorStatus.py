class MotorStatus():

    def __init__(self, bitfield):
        """
        initialize with 24-bit integer bitfield
        """
        self.bitfield = bitfield

    def direction(self):
        return 'forward' if (self.bitfield & (1 << 1)) else 'reverse'

    def isRunning(self):
        return bool(self.bitfield & (1 << 2))

    def isResponding(self):
        return not bool(self.bitfield & (1 << 3))

    def isBursting(self):
        return bool(self.bitfield & (1 << 4))

    def isTimedFreeRunning(self):
        return bool(self.bitfield & (1 << 5))

    def isHostControlEstablished(self):
        return bool(self.bitfield & (1 << 7))

    def isForwardLimitReached(self):
        return bool(self.bitfield & (1 << 9))

    def isBackwardLimitReached(self):
        return bool(self.bitfield & (1 << 10))

    def burstAmplitudeMode(self):
        return 'burst' if (self.bitfield & (1 << 11)) else 'amplitude'

    def isBackgroundJobActive(self):
        return bool(self.bitfield & (1 << 15))

    def encoderError(self):
        return bool(self.bitfield & (1 << 16))

    def isZeroReferenceEnabled(self):
        return bool(self.bitfield & (1 << 17))

    def isOnTarget(self):
        return bool(self.bitfield & (1 << 18))

    def isMovingTowardTarget(self):
        return bool(self.bitfield & (1 << 19))

    def isMaintenanceModeEnabled(self):
        return bool(self.bitfield & (1 << 20))

    def isClosedLoopEnabled(self):
        return bool(self.bitfield & (1 << 21))

    def isAccelerating(self):
        return bool(self.bitfield & (1 << 22))

    def isStalled(self):
        return bool(self.bitfield & (1 << 23))

    def pprint(self, newline=False):
        print('Direction: ', self.direction())
        print('Running: ', self.isRunning())
        print('Responding: ', self.isResponding())
        print('Bursting: ', self.isResponding())
        print('Timed Free Running: ', self.isTimedFreeRunning())
        print('Host Control Established: ', self.isHostControlEstablished())
        print('Forward Limit Reached: ', self.isForwardLimitReached())
        print('Backward Limit Reached: ', self.isBackwardLimitReached())
        print('Burst/Amplitude Mode: ', self.burstAmplitudeMode())
        print('Background Job Active: ', self.isBackgroundJobActive())
        print('Encoder Error: ', self.encoderError())
        print('Zero Reference Enabled: ', self.isZeroReferenceEnabled())
        print('On Target: ', self.isOnTarget())
        print('Moving Toward Target: ', self.isMovingTowardTarget())
        print('Maintenance Mode Enabled: ', self.isMaintenanceModeEnabled())
        print('Closed Loop Enabled: ', self.isClosedLoopEnabled())
        print('Accelerating: ', self.isAccelerating())
        print('Stalled: ', self.isStalled())
        if newline: print()

