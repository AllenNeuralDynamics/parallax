import pyqtgraph as pg
import coorx
from parallax.mock_sim import GraphicsView3D, CheckerBoard, Axis, Electrode, calibrate_camera, undistort_image
from parallax.lib import find_checker_corners

class StereoView(pg.QtWidgets.QWidget):
    def __init__(self, parent=None, background=(128, 128, 128)):
        pg.QtWidgets.QWidget.__init__(self, parent)
        self.layout = pg.QtWidgets.QHBoxLayout()
        self.setLayout(self.layout)
        self.views = [GraphicsView3D(parent=self), GraphicsView3D(parent=self)]
        for v in self.views:
            self.layout.addWidget(v)
            v.setBackground(pg.mkColor(background))

    def set_camera(self, cam, **kwds):
        self.views[cam].set_camera(**kwds)



if __name__ == '__main__':
    # pg.dbg()

    app = pg.mkQApp()
    win = StereoView()
    win.resize(1600, 600)
    win.show()

    camera_params = dict(
        pitch=30,
        distance=15,
        distortion=(-0.1, 0.01, -0.001, 0, 0),
        # distortion=(2.49765866e-02, -1.10638222e+01, -1.22811774e-04, 4.89346001e-03, -3.28053580e-01),
    )
    win.set_camera(0, yaw=-5, **camera_params)
    win.set_camera(1, yaw=5, **camera_params)

    cb_size = 8
    checkers = CheckerBoard(views=win.views, size=cb_size, colors=[0.1, 0.9])
    checkers.transform.set_params(offset=[-cb_size/2, -cb_size/2, 0])
    axis = Axis(views=win.views)

    s = 0.1
    # electrodes = []
    # for i in range(4):
    #     e = Electrode(win.views)
    #     electrodes.append(e)

    #     e.transform = coorx.AffineTransform(dims=(3, 3))
    #     e.transform.scale([s, s, s])
    #     e.transform.rotate(60, [1, 0, 0])
    #     e.transform.translate([0, 1, 1])
    #     e.transform.rotate(15*i, [0, 0, 1])


    # tr = coorx.AffineTransform(dims=(3, 3))
    # tr.translate([-2.5, -2.5, 0])
    # tr.scale(0.5)
    # tr.rotate(30, [1, 0, 0])
    # tr.rotate(45, [0, 0, 1]) 

    def test(n_images=10):
        view = win.views[0]
        ret, mtx, dist, rvecs, tvecs = calibrate_camera(view, n_images=n_images, cb_size=(cb_size-1, cb_size-1))
        print(f"Distortion coefficients: {dist}")
        print(f"Intrinsic matrix: {mtx}")
        pg.image(undistort_image(view.get_array().transpose(1, 0, 2), mtx, dist))
        return mtx, dist


    def test2():
        """Can we invert opencv's undistortion?
        """
        ret, mtx, dist, rvecs, tvecs = calibrate_camera(win.views[0], n_images=10, cb_size=(cb_size-1, cb_size-1))
        print(mtx)
        print(dist)
        img = win.views[0].get_array()
        uimg = undistort_image(img, mtx, dist)
        v1 = pg.image(img.transpose(1, 0, 2))
        v2 = pg.image(uimg.transpose(1, 0, 2))
        tr = coorx.AffineTransform(matrix=mtx[:2, :2], offset=mtx[:2, 2])
        ltr = coorx.nonlinear.LensDistortionTransform(dist[0])
        ttr = coorx.CompositeTransform([tr.inverse, ltr, tr])

        objp, imgp = find_checker_corners(uimg, board_shape=(cb_size-1, cb_size-1))
        undistorted_pts = imgp[:, 0, :]

        distorted_pts = ttr.map(undistorted_pts)

        s1 = pg.ScatterPlotItem(x=undistorted_pts[:,0], y=undistorted_pts[:,1], brush='r', pen=None)
        v2.view.addItem(s1)

        s2 = pg.ScatterPlotItem(x=distorted_pts[:,0], y=distorted_pts[:,1], brush='r', pen=None)
        v1.view.addItem(s2)
