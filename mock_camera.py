import pyqtgraph as pg
import cv2 as cv
import numpy as np
import coorx
from parallax.calibration import CameraTransform, StereoCameraTransform


class PerspectiveTransform(coorx.BaseTransform):
    """3D perspective or orthographic matrix transform using homogeneous coordinates.

    Assumes a camera at the origin, looking toward the -Z axis.
    The camera's top points toward +Y, and right points toward +X.

    Points inside the perspective frustum are mapped to the range [-1, +1] along all three axes.
    """
    def __init__(self):
        super().__init__(dims=(3, 3))
        self.affine = coorx.AffineTransform(dims=(4, 4))

    def _map(self, arr):
        arr4 = np.empty((arr.shape[0], 4), dtype=arr.dtype)
        arr4[:, :3] = arr
        arr4[:, 3] = 1
        out = self.affine._map(arr4)
        return out[:, :3] / out[:, 3:4]

    def set_ortho(self, left, right, bottom, top, znear, zfar):
        """Set orthographic transform.
        """
        assert(right != left)
        assert(bottom != top)
        assert(znear != zfar)

        M = np.zeros((4, 4), dtype=np.float32)
        M[0, 0] = +2.0 / (right - left)
        M[3, 0] = -(right + left) / float(right - left)
        M[1, 1] = +2.0 / (top - bottom)
        M[3, 1] = -(top + bottom) / float(top - bottom)
        M[2, 2] = -2.0 / (zfar - znear)
        M[3, 2] = -(zfar + znear) / float(zfar - znear)
        M[3, 3] = 1.0
        self.affine.matrix = M.T

    def set_perspective(self, fovy, aspect, znear, zfar):
        """Set the perspective

        Parameters
        ----------
        fov : float
            Field of view.
        aspect : float
            Aspect ratio.
        near : float
            Near location.
        far : float
            Far location.
        """
        assert(znear != zfar)
        h = np.tan(fovy * np.pi / 360.0) * znear
        w = h * aspect
        self.set_frustum(-w, w, -h, h, znear, zfar)

    def set_frustum(self, left, right, bottom, top, near, far):  # noqa
        """Set the frustum
        """
        M = frustum(left, right, bottom, top, near, far)
        self.affine.matrix = M.T


def frustum(left, right, bottom, top, znear, zfar):
    """Create view frustum

    Parameters
    ----------
    left : float
        Left coordinate of the field of view.
    right : float
        Right coordinate of the field of view.
    bottom : float
        Bottom coordinate of the field of view.
    top : float
        Top coordinate of the field of view.
    znear : float
        Near coordinate of the field of view.
    zfar : float
        Far coordinate of the field of view.

    Returns
    -------
    M : ndarray
        View frustum matrix (4x4).
    """
    assert(right != left)
    assert(bottom != top)
    assert(znear != zfar)

    M = np.zeros((4, 4))
    M[0, 0] = +2.0 * znear / float(right - left)
    M[2, 0] = (right + left) / float(right - left)
    M[1, 1] = +2.0 * znear / float(top - bottom)
    M[2, 1] = (top + bottom) / float(top - bottom)
    M[2, 2] = -(zfar + znear) / float(zfar - znear)
    M[3, 2] = -2.0 * znear * zfar / float(zfar - znear)
    M[2, 3] = -1.0
    return M


class RadialDistortionTransform(coorx.BaseTransform):
    def __init__(self, k=(0, 0, 0)):
        super().__init__(dims=(3, 3))
        self.k = k

    def set_k(self, k):
        self.k = k
        self._update()

    def _map(self, arr):
        r = np.linalg.norm(arr, axis=1)
        dist = (1 + self.k[0] * r**2 + self.k[1] * r**4 + self.k[2] * r**6)
        out = np.empty_like(arr)
        # distort x,y
        out[:, :2] = arr[:, :2] * dist[:, None]
        # leave other axes unchanged
        out[:, 2:] = arr[:, 2:]
        return out


class CameraTransform(coorx.CompositeTransform):
    def __init__(self):
        self.view = coorx.SRT3DTransform()
        self.proj = PerspectiveTransform()
        self.dist = RadialDistortionTransform()
        self.screen = coorx.STTransform(dims=(3, 3))
        super().__init__([self.view, self.proj, self.dist, self.screen])

    def set_camera(self, center, look, fov, screen_size, up=(0, 0, 1), distortion=(0, 0, 0)):
        center = np.asarray(center)
        look = np.asarray(look)
        up = np.asarray(up)

        aspect_ratio = screen_size[0] / screen_size[1]
        look_dist = np.linalg.norm(look - center)
        forward = look - center
        forward /= np.linalg.norm(forward)
        right = np.cross(forward, up)
        right /= np.linalg.norm(right)
        up = np.cross(right, forward)
        up /= np.linalg.norm(up)

        pts1 = np.array([center, center + forward, center + right, center + up])
        pts2 = np.array([[0, 0, 0], [0, 0, -1], [1, 0, 0], [0, 1, 0]])
        self._view_mapping_err = self.view.set_mapping(pts1, pts2)

        self.proj.set_perspective(fov, aspect_ratio, look_dist / 100, look_dist * 100)

        self.screen.set_mapping(
            [[-1, -1, -1], [1, 1, 1]],
            [[0, screen_size[1], 0], [screen_size[0], 0, 1]]
        )

        self.dist.set_k(distortion)


class GraphicsItem:
    def __init__(self, view):
        self.view = view
        self.full_transform = coorx.CompositeTransform([])
        self.transform = coorx.SRT3DTransform()
        self.items = []
        self.scene = view.scene()
        self.full_transform.add_change_callback(self.transform_changed)

    @property
    def transform(self):
        return self._transform

    @transform.setter
    def transform(self, tr):
        self._transform = tr
        self.full_transform.transforms = [tr, self.view.camera_tr]

    def render(self):
        self.clear_graphics_items()
        for item in self.items:
            pts = None
            if 'points' in item:
                pts = self.full_transform.map(item['points'])
                pts_xy = pts[:, :2]
                pts_z = pts[:, 2]

            if item['type'] == 'poly':
                polygon = pg.QtGui.QPolygonF([pg.QtCore.QPointF(*pt) for pt in pts_xy])
                polygon_item = pg.QtWidgets.QGraphicsPolygonItem(polygon)
                item['graphicsItem'] = polygon_item
            elif item['type'] == 'line':
                line_item = pg.QtWidgets.QGraphicsLineItem(*pts_xy.flatten())
                item['graphicsItem'] = line_item
            elif item['type'] == 'plot':
                line_item = pg.PlotCurveItem(x=pts_xy[:,0], y=pts_xy[:,1])
                item['graphicsItem'] = line_item
            else:
                raise TypeError(item['type'])

            if 'pen' in item:
                pen = pg.mkPen(item['pen'])
                item['graphicsItem'].setPen(pen)

            if 'brush' in item:
                brush = pg.mkBrush(item['brush'])
                item['graphicsItem'].setBrush(brush)

            item['graphicsItem'].setZValue(-pts_z.mean())

            self.scene.addItem(item['graphicsItem'])

    def clear_graphics_items(self):
        for item in self.items:
            gfxitem = item.pop('graphicsItem', None)
            if gfxitem is not None:
                self.scene.removeItem(gfxitem)

    def add_items(self, items):
        self.items.extend(items)
        self.render()

    def transform_changed(self, event):
        self.render()


class CheckerBoard(GraphicsItem):
    def __init__(self, view, size, colors):
        super().__init__(view)

        for i in range(size):
            for j in range(size):
                self.items.append({
                    'type': 'poly',
                    'points': [[i, j, 0], [i+1, j, 0], [i+1, j+1, 0], [i, j+1, 0], [i, j, 0]],
                    'pen': None,
                    'brush': colors[(i  + j) % 2],
                })
        self.render()


class Axis(GraphicsItem):
    def __init__(self, view):
        super().__init__(view)

        self.items = [
            {'type': 'line', 'points': [[0, 0, 0], [1, 0, 0]], 'pen': 'r'},
            {'type': 'line', 'points': [[0, 0, 0], [0, 1, 0]], 'pen': 'g'},
            {'type': 'line', 'points': [[0, 0, 0], [0, 0, 1]], 'pen': 'b'},
        ]
        self.render()


class Electrode(GraphicsItem):
    def __init__(self, view):    
        super().__init__(view)

        self.items = [
            {'type': 'poly', 'pen': None, 'brush': 0.2, 'points': [
                [0, 0, 0], [1, 0, 1], [1, 0, 100], [-1, 0, 100], [-1, 0, 1], [0, 0, 0]
            ]},
        ]
        self.render()


class GraphicsView3D(pg.GraphicsView):
    def __init__(self, **kwds):
        self.camera_tr = CameraTransform()
        self.press_event = None
        self.camera_params = {'look': [0, 0, 0], 'pitch': 30, 'yaw': 0, 'dist': 10, 'fov': 45, 'distortion': (0, 0, 0)}
        super().__init__(**kwds)
        self.setRenderHint(pg.QtGui.QPainter.Antialiasing)
        self.set_camera(look=[0, 0, 0], pitch=30, yaw=0, dist=10, fov=45)

    def set_camera(self, **kwds):
        for k,v in kwds.items():
            assert k in self.camera_params
            self.camera_params[k] = v
        self.update_camera()

    def update_camera(self):
        p = self.camera_params
        look = np.asarray(p['look'])
        pitch = p['pitch'] * np.pi/180
        hdist = p['dist'] * np.cos(pitch)
        yaw = p['yaw'] * np.pi/180
        cam_pos = look + np.array([
            hdist * np.cos(yaw),
            hdist * np.sin(yaw),
            p['dist'] * np.sin(pitch)
        ])
        self.camera_tr.set_camera(center=cam_pos, look=look, fov=p['fov'], screen_size=[self.width(), self.height()], distortion=p['distortion'])

    def mousePressEvent(self, ev):
        self.press_event = ev
        self.last_mouse_pos = ev.pos()
        ev.accept()

    def mouseMoveEvent(self, ev):
        if self.press_event is None:
            return
        dif = ev.pos() - self.last_mouse_pos        
        self.last_mouse_pos = ev.pos()

        self.camera_params['pitch'] += dif.y()
        self.camera_params['yaw'] -= dif.x()
        self.update_camera()

    def mouseReleaseEvent(self, ev):
        self.press_event = None

    def wheelEvent(self, event):
        self.camera_params['dist'] *= 1.01**event.angleDelta().y()
        self.update_camera()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self.update_camera()

    def get_array(self):
        return pg.imageToArray(pg.QtGui.QImage(self.grab()), copy=True)


def find_checker_corners(img, board_shape, show=False):
    """https://docs.opencv.org/4.x/dc/dbb/tutorial_py_calibration.html
    """
    if show:
        view = pg.image(img)

    criteria = (cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER, 30, 0.001)

    # prepare object points, like (0,0,0), (1,0,0), (2,0,0) ....,(6,5,0)
    objp = np.zeros((board_shape[0] * board_shape[1], 3), dtype='float32')
    objp[:, :2] = np.mgrid[0:board_shape[0], 0:board_shape[1]].T.reshape(-1, 2)

    gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)

    # Find the chess board corners
    ret, corners = cv.findChessboardCorners(gray, board_shape, None)
    if not ret:
        return None, None

    # If found, add object points, image points (after refining them)
    imgp = cv.cornerSubPix(gray, corners, (11,11), (-1,-1), criteria)

    if show:
        plt = pg.ScatterPlotItem(x=imgp[:, 0, 1], y=imgp[:, 0, 0])
        view.view.addItem(plt)

    return objp, imgp


def generate_calibration_data(view, size):
    imgp = []
    objp = []
    cam = view.camera_params.copy()
    for i in range(size*4):
        pitch = np.random.uniform(45, 89)
        yaw = np.random.uniform(0, 360)
        distance = np.random.uniform(5, 15)
        view.set_camera(pitch=pitch, yaw=yaw, dist=distance)
        op,ip = find_checker_corners(view.get_array(), (4, 4))
        if op is None:
            continue
        objp.append(op)
        imgp.append(ip)
        if len(imgp) >= size:
            break
        app.processEvents()
    view.set_camera(**cam)
    return objp, imgp


def calibrate_camera(view, size=40):
    objp, imgp = generate_calibration_data(view, size=size)
    ret, mtx, dist, rvecs, tvecs = cv.calibrateCamera(objp, imgp, (view.width(), view.height()), None, None)
    return ret, mtx, dist, rvecs, tvecs


def undistort_image(img, mtx, dist):
    h, w = img.shape[:2]
    new_camera_mtx, roi = cv.getOptimalNewCameraMatrix(mtx, dist, (w,h), 1, (w,h))

    # undistort
    mapx, mapy = cv.initUndistortRectifyMap(mtx, dist, None, new_camera_mtx, (w,h), 5)
    dst = cv.remap(img, mapx, mapy, cv.INTER_LINEAR)

    # crop the image
    x, y, w, h = roi
    dst = dst[y:y+h, x:x+w]
    return dst


if __name__ == '__main__':
    # pg.dbg()

    screen_size = (800, 600)

    app = pg.mkQApp()
    win = GraphicsView3D()
    win.setBackground(pg.mkColor(128, 128, 128))
    win.resize(*screen_size)
    win.show()

    win.set_camera(distortion=(-0.03, 0, 0))

    checkers = CheckerBoard(win, size=5, colors=[0.1, 0.9])
    checkers.transform.set_params(offset=[-2.5, -2.5, -1])
    axis = Axis(win)

    # s = 0.1
    # electrodes = []
    # for i in range(4):
    #     e = Electrode(win)
    #     electrodes.append(e)
    #     e.transform.scale([s, s, s])
    #     e.transform.translate([0, 0, 5])
    #     e.transform.rotate(45, [1, 0, 0])
    #     e.transform.rotate(15 * i, [0, 0, 1])


    tr = coorx.AffineTransform(dims=(3, 3))
    tr.translate([-2.5, -2.5, 0])
    tr.scale(0.5)
    tr.rotate(30, [1, 0, 0])
    tr.rotate(45, [0, 0, 1]) 

    def test():
        ret, mtx, dist, rvecs, tvecs = calibrate_camera(win)
        print(dist)
        pg.image(undistort_image(win.get_array(), mtx, dist))