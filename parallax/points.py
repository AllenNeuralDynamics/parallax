import random
import string
import numpy as np


class Point3D:

    def __init__(self, name=None):
        self.name = ''.join(random.choice(string.ascii_uppercase + \
                                            string.ascii_lowercase + \
                                            string.digits) for _ in range(8))
        self.cs = 'default'
        self.x = 0.
        self.y = 0.
        self.z = 0.
        self.img_points = (-1, -1, -1, -1)

    def set_name(self, name):
        self.name = name

    def set_coordinate_system(self, cs):
        self.cs = cs

    def set_coordinates(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

    def get_coordinates_tuple(self):
        return (self.x, self.y, self.z)

    def get_coordinates_array(self):
        return np.array([self.x, self.y, self.z], dtype=np.float32)

    def set_img_points(self, img_points):
        self.img_points = img_points

    def get_img_points(self):
        return self.img_points


