""" Test for camera """
#!/usr/bin/env python -i
from parallax.camera import list_cameras, close_cameras

# test code: captures an image and reports resolution
import sys
cameras = list_cameras()

print(f"{len(cameras)} camera{'s' if cameras else ''} detected")
if not cameras:
    sys.exit(0)
for camera in cameras:
    print("  ", camera.name())

camera = cameras[0]
camera.capture()
data = camera.get_last_image_data()
print('image size: ', data.shape)
print('flags:\n', data.flags)

# clean up
close_cameras()
