import pyqtgraph as pg
import cv2 as cv
import numpy as np
import coorx
from parallax.calibration import CameraTransform, StereoCameraTransform
from parallax.lib import find_checker_corners
from parallax.config import config


class CameraTransform(coorx.CompositeTransform):
    def __init__(self):
        self.view = coorx.SRT3DTransform()
        self.proj = coorx.linear.PerspectiveTransform()
        self.dist = coorx.nonlinear.LensDistortionTransform()
        self.dist_embed = coorx.util.AxisSelectionEmbeddedTransform(axes=[0, 1], transform=self.dist, dims=(3, 3))
        self.screen = coorx.STTransform(dims=(3, 3))
        super().__init__([self.view, self.proj, self.dist_embed, self.screen])

    def set_camera(self, center, look, fov, screen_size, up=(0, 0, 1), distortion=(0, 0, 0, 0, 0)):
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


        near = look_dist / 100
        far = look_dist * 100

        # set perspective with aspect=1 so that distortion is performed on
        # isotropic coordinates
        self.proj.set_perspective(fov, 1.0, near, far)

        # correct for aspect in the screen transform instead
        self.screen.set_mapping(
            [[-1, -1 / aspect_ratio, -1], [1, 1 / aspect_ratio, 1]],
            [[0, screen_size[1], 0], [screen_size[0], 0, 1]]
        )

        self.dist.set_coeff(distortion)


class GraphicsItem:
    def __init__(self, views):
        self._transform = coorx.SRT3DTransform()
        self.items = []
        self.item_views = []
        for view in views:
            self.add_view(view)

    def add_view(self, view):
        self.item_views.append(GraphicsItemView(self, view))
        self.render()

    @property
    def transform(self):
        return self._transform

    @transform.setter
    def transform(self, tr):
        self._transform = tr
        for view in self.item_views:
            view.update_transform()

    def add_items(self, items):
        self.items.extend(items)
        self.render()

    def render(self):
        for view in self.item_views:
            view.render()


class GraphicsItemView:
    def __init__(self, item, view):
        self.item = item
        self.view = view
        self.full_transform = coorx.CompositeTransform([])
        self.update_transform()
        self.scene = view.scene()
        self.full_transform.add_change_callback(self.transform_changed)

    def update_transform(self):
        self.full_transform.transforms = [self.item.transform, self.view.camera_tr]

    def transform_changed(self, event):
        self.render()

    def render(self):
        self.clear_graphics_items()
        for item in self.item.items:
            pts = None
            if 'points' in item:
                pts = self.full_transform.map(item['points'])
                pts_xy = pts[:, :2]
                pts_z = pts[:, 2]

            if item['type'] == 'poly':
                polygon = pg.QtGui.QPolygonF([pg.QtCore.QPointF(*pt) for pt in pts_xy])
                gfx_item = pg.QtWidgets.QGraphicsPolygonItem(polygon)
            elif item['type'] == 'line':
                gfx_item = pg.QtWidgets.QGraphicsLineItem(*pts_xy.flatten())
            elif item['type'] == 'plot':
                gfx_item = pg.PlotCurveItem(x=pts_xy[:,0], y=pts_xy[:,1])
            else:
                raise TypeError(item['type'])

            if 'pen' in item:
                pen = pg.mkPen(item['pen'])
                gfx_item.setPen(pen)

            if 'brush' in item:
                brush = pg.mkBrush(item['brush'])
                gfx_item.setBrush(brush)

            gfx_item.setZValue(-pts_z.mean())
            item.setdefault('graphicsItems', {})
            item['graphicsItems'][self] = gfx_item
            self.scene.addItem(gfx_item)

    def clear_graphics_items(self):
        for item in self.item.items:
            gfxitems = item.get('graphicsItems', {})
            gfxitem = gfxitems.pop(self, None)
            if gfxitem is not None:
                self.scene.removeItem(gfxitem)


class CheckerBoard(GraphicsItem):
    def __init__(self, views, size, colors):
        super().__init__(views)

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
    def __init__(self, views):
        super().__init__(views)

        self.items = [
            {'type': 'line', 'points': [[0, 0, 0], [1, 0, 0]], 'pen': 'r'},
            {'type': 'line', 'points': [[0, 0, 0], [0, 1, 0]], 'pen': 'g'},
            {'type': 'line', 'points': [[0, 0, 0], [0, 0, 1]], 'pen': 'b'},
        ]
        self.render()


class Electrode(GraphicsItem):
    def __init__(self, views):    
        super().__init__(views)
        w = 70
        l = 10e3
        self.items = [
            {'type': 'poly', 'pen': None, 'brush': 0.2, 'points': [
                [0, 0, 0], [w, 0, w], [w, 0, l], [-w, 0, l], [-w, 0, l], [0, 0, 0]
            ]},
        ]
        self.render()


class GraphicsView3D(pg.GraphicsView):
    def __init__(self, **kwds):
        self.camera_tr = CameraTransform()
        self.press_event = None
        self.camera_params = {'look': [0, 0, 0], 'pitch': 30, 'yaw': 0, 'distance': 10, 'fov': 45, 'distortion': (0, 0, 0, 0, 0)}
        super().__init__(**kwds)
        self.setRenderHint(pg.QtGui.QPainter.Antialiasing)
        self.set_camera(look=[0, 0, 0], pitch=30, yaw=0, distance=10, fov=45)

    def set_camera(self, **kwds):
        for k,v in kwds.items():
            assert k in self.camera_params
            self.camera_params[k] = v
        self.update_camera()

    def update_camera(self):
        p = self.camera_params
        look = np.asarray(p['look'])
        pitch = p['pitch'] * np.pi/180
        hdist = p['distance'] * np.cos(pitch)
        yaw = p['yaw'] * np.pi/180
        cam_pos = look + np.array([
            hdist * np.cos(yaw),
            hdist * np.sin(yaw),
            p['distance'] * np.sin(pitch)
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

        self.camera_params['pitch'] = np.clip(self.camera_params['pitch'] + dif.y(), -90, 90)
        self.camera_params['yaw'] -= dif.x()
        self.update_camera()

    def mouseReleaseEvent(self, ev):
        self.press_event = None

    def wheelEvent(self, event):
        self.camera_params['distance'] *= 1.01**event.angleDelta().y()
        self.update_camera()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self.update_camera()

    def get_array(self):
        arr = pg.imageToArray(pg.QtGui.QImage(self.grab()), copy=True, transpose=False)[..., :3]
        return arr


def generate_calibration_data(view, n_images, cb_size):
    app = pg.QtWidgets.QApplication.instance()
    imgp = []
    objp = []
    cam = view.camera_params.copy()
    for i in range(n_images*4):
        pitch = np.random.uniform(45, 89)
        yaw = np.random.uniform(0, 360)
        distance = np.random.uniform(5, 15)
        view.set_camera(pitch=pitch, yaw=yaw, distance=distance)
        op,ip = find_checker_corners(view.get_array(), cb_size)
        if op is None:
            continue
        objp.append(op)
        imgp.append(ip)
        if len(imgp) >= n_images:
            break
        app.processEvents()
    view.set_camera(**cam)
    return objp, imgp


def calibrate_camera(view, cb_size, n_images=40):
    objp, imgp = generate_calibration_data(view, n_images=n_images, cb_size=cb_size)
    ret, mtx, dist, rvecs, tvecs = cv.calibrateCamera(objp, imgp, (view.width(), view.height()), None, None)
    return ret, mtx, dist, rvecs, tvecs


def undistort_image(img, mtx, dist, optimize=False, crop=False):
    h, w = img.shape[:2]
    if optimize:
        new_camera_mtx, roi = cv.getOptimalNewCameraMatrix(mtx, dist, (w,h), 1, (w,h))
    else:
        assert crop is False
        new_camera_mtx = mtx
        
    # undistort
    mapx, mapy = cv.initUndistortRectifyMap(mtx, dist, None, new_camera_mtx, (w,h), 5)
    dst = cv.remap(img, mapx, mapy, cv.INTER_LINEAR)

    # crop the image
    if crop:
        x, y, w, h = roi
        dst = dst[y:y+h, x:x+w]
    return dst


class MockSim(pg.QtCore.QObject):

    _instance = None

    stage_moved = pg.QtCore.Signal(object)

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = MockSim()
        return cls._instance

    def __init__(self):
        pg.QtCore.QObject.__init__(self)
        self.cameras = {}
        self.stages = {}

        self.items = []
        if config['mock_sim']['show_checkers']:
            cb_size = 8
            checkers = CheckerBoard(views=[], size=cb_size, colors=[0.4, 0.6])
            s = 1e3
            checkers.transform.set_params(offset=[-s*cb_size/2, -s*cb_size/2, -2000], scale=[s, s, s])
            self.items.append(checkers)

        if config['mock_sim']['show_axes']:
            axis = Axis(views=[])
            axis.transform.set_params(scale=[s, s, s])
            self.items.append(axis)

        self.stage_moved.connect(self.update_stage)
    
    def add_camera(self, cam):
        view = GraphicsView3D(background=(128, 128, 128))
        view.resize(*cam.sensor_size)
        view.set_camera(**cam.camera_params)
        view.scene().changed.connect(self.clear_frames)
        self.cameras[cam] = {'view': view, 'frame': None}

        for item in self.items:
            item.add_view(view)

    def clear_frames(self):
        for v in self.cameras.values():
            v['frame'] = None

    def get_camera_frame(self, cam):
        if self.cameras[cam]['frame'] is None:
            view = self.cameras[cam]['view']
            self.cameras[cam]['frame'] = view.get_array()
        return self.cameras[cam]['frame']

    def add_stage(self, stage):
        views = [c['view'] for c in self.cameras.values()]
        item = Electrode(views=views)

        tr = coorx.AffineTransform(dims=(3, 3))
        theta, phi = stage.orientation()
        # s = 1e3
        # tr.scale([s, s, s])
        tr.rotate(phi, [1, 0, 0])
        tr.rotate(theta, [0, 0, 1])
        item.transform = tr

        self.stages[stage] = {'item': item}
        stage.add_move_callback(self._stage_moved_cb)
    
    def _stage_moved_cb(self, stage):
        # callback is invoked in thread; send to gui thread by signal
        self.stage_moved.emit(stage)

    def update_stage(self, stage):    
        pos = stage.get_tip_position()
        item = self.stages[stage]['item']
        item.transform.offset = pos
