class MotorStatus():

    def __init__(self, bitfield, position):
        """
        initialize with 24-bit integer bitfield
        """
        self.bitfield = bitfield
        self.position = position

    def direction(self):
        return 'forward' if (self.bitfield & (1 << 1)) else 'reverse'

    def is_running(self):
        return bool(self.bitfield & (1 << 2))

    def is_responding(self):
        return not bool(self.bitfield & (1 << 3))

    def is_bursting(self):
        return bool(self.bitfield & (1 << 4))

    def is_timed_free_running(self):
        return bool(self.bitfield & (1 << 5))

    def is_host_control_established(self):
        return bool(self.bitfield & (1 << 7))

    def is_forward_limit_reached(self):
        return bool(self.bitfield & (1 << 9))

    def is_backward_limit_reached(self):
        return bool(self.bitfield & (1 << 10))

    def burst_amplitude_mode(self):
        return 'burst' if (self.bitfield & (1 << 11)) else 'amplitude'

    def is_background_job_active(self):
        return bool(self.bitfield & (1 << 15))

    def encoder_error(self):
        return bool(self.bitfield & (1 << 16))

    def is_zero_reference_enabled(self):
        return bool(self.bitfield & (1 << 17))

    def is_on_target(self):
        return bool(self.bitfield & (1 << 18))

    def is_moving_toward_target(self):
        return bool(self.bitfield & (1 << 19))

    def is_maintenance_mode_enabled(self):
        return bool(self.bitfield & (1 << 20))

    def is_closed_loop_enabled(self):
        return bool(self.bitfield & (1 << 21))

    def is_accelerating(self):
        return bool(self.bitfield & (1 << 22))

    def is_stalled(self):
        return bool(self.bitfield & (1 << 23))

    def pprint(self, newline=False):
        print('Direction: ', self.direction())
        print('Running: ', self.is_running())
        print('Responding: ', self.is_responding())
        print('Bursting: ', self.is_responding())
        print('Timed Free Running: ', self.is_timed_free_running())
        print('Host Control Established: ', self.is_host_control_established())
        print('Forward Limit Reached: ', self.is_forward_limit_reached())
        print('Backward Limit Reached: ', self.is_backward_limit_reached())
        print('Burst/Amplitude Mode: ', self.burst_amplitude_mode())
        print('Background Job Active: ', self.is_background_job_active())
        print('Encoder Error: ', self.encoder_error())
        print('Zero Reference Enabled: ', self.is_zero_reference_enabled())
        print('On Target: ', self.is_on_target())
        print('Moving Toward Target: ', self.is_moving_toward_target())
        print('Maintenance Mode Enabled: ', self.is_maintenance_mode_enabled())
        print('Closed Loop Enabled: ', self.is_closed_loop_enabled())
        print('Accelerating: ', self.is_accelerating())
        print('Stalled: ', self.is_stalled())
        print('')
        print('Position: ', self.position)
        if newline: print()

    def get_position(self):
        return self.position

