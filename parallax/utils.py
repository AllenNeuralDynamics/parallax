import cv2

class UtilsCoords:
    def __init__(self, original_size, resized_size):
        self.original_size = original_size
        self.resized_size = resized_size

    def scale_coords_to_original(self, tip):
        x, y = tip
        original_width, original_height = self.original_size
        resized_width, resized_height = self.resized_size

        scale_x = original_width / resized_width
        scale_y = original_height / resized_height

        original_x = int(x * scale_x)
        original_y = int(y * scale_y)

        return original_x, original_y

class UtilsCrops:
    def __init__(self):
        pass

    def calculate_crop_region(self, tip, base, crop_size, IMG_SIZE):
        tip_x, tip_y = tip
        base_x, base_y = base
        top = max(min(tip_y, base_y) - crop_size, 0)
        bottom = min(max(tip_y, base_y) + crop_size, IMG_SIZE[1])
        left = max(min(tip_x, base_x) - crop_size, 0)
        right = min(max(tip_x, base_x) + crop_size, IMG_SIZE[0])
        return top, bottom, left, right

    def is_point_on_crop_region(self, point, top, bottom, left, right, buffer=5):
        x, y = point
        return (top - buffer <= y <= top + buffer) or \
               (bottom - buffer <= y <= bottom + buffer) or \
               (left - buffer <= x <= left + buffer) or \
               (right - buffer <= x <= right + buffer)
