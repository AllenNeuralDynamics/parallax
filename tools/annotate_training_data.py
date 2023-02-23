import pyqtgraph as pg
import json


class MainWindow(pg.GraphicsView):
    def __init__(self, meta_file, img_files):
        super().__init__()
        self.img_files = img_files

        self.view = pg.ViewBox()
        self.view.invertY()
        self.setCentralItem(self.view)

        self.img_item = pg.QtWidgets.QGraphicsPixmapItem()
        self.view.addItem(self.img_item)

        self.line_item = pg.QtWidgets.QGraphicsLineItem()
        self.line_item.setPen(pg.mkPen('r'))
        self.circle_item = pg.QtWidgets.QGraphicsEllipseItem()
        self.circle_item.setPen(pg.mkPen('r'))
        self.view.addItem(self.line_item)
        self.view.addItem(self.circle_item)

        self.next_click = 0
        self.attached_pt = None
        self.loaded_file = None

        self.meta_file = meta_file
        if os.path.exists(meta_file):
            self.meta = json.load(open(meta_file, 'r'))
        else:
            self.meta = {}

        self.load_image(0)

    def keyPressEvent(self, ev):
        if ev.key() == pg.QtCore.Qt.Key_Left:
            self.load_image(self.current_index - 1)
        elif ev.key() == pg.QtCore.Qt.Key_Right:
            self.load_image(self.current_index + 1)
        else:
            print(ev.key())

    def mousePressEvent(self, ev):
        # print('press', ev)
        if ev.button() == pg.QtCore.Qt.LeftButton:
            self.attached_pt = self.next_click
            self.update_pos(ev.pos())
            ev.accept()
            return
        # return super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        # print('release', ev)
        self.attached_pt = None
        self.next_click = (self.next_click + 1) % 2

    def mouseMoveEvent(self, ev):
        # print('move', ev)
        self.update_pos(ev.pos())
        ev.accept()

    def update_pos(self, pos):
        pos = self.view.mapDeviceToView(pos)
        if self.attached_pt == 0:
            self.set_pts(pos, None)
        elif self.attached_pt == 1:
            self.set_pts(None, pos)
        else:
            return
        self.update_meta()

    def set_pts(self, pt1, pt2):
        line = self.line_item.line()
        if pt1 is not None:
            line.setP1(pt1)
            self.circle_item.setRect(pt1.x()-10, pt1.y()-10, 20, 20)
            self.circle_item.setVisible(True)
        if pt2 is not None:
            line.setP2(pt2)
        self.line_item.setVisible(True)
        self.line_item.setLine(line)

    def hide_line(self):
        self.line_item.setVisible(False)
        self.circle_item.setVisible(False)

    def update_meta(self):
        line = self.line_item.line()
        self.meta[self.loaded_file] = {
            'pt1': (line.x1(), line.y1()),
            'pt2': (line.x2(), line.y2()),
        } 
        json.dump(self.meta, open(self.meta_file, 'w'))

    def load_image(self, index):
        filename = self.img_files[index]
        pxm = pg.QtGui.QPixmap()
        pxm.load(filename)
        self.img_item.setPixmap(pxm)
        self.img_item.pxm = pxm
        self.view.autoRange(padding=0)
        self.current_index = index
        self.setWindowTitle(filename)
        self.loaded_file = filename

        meta = self.meta.get(filename, {})
        pt1 = meta.get('pt1', None)
        pt2 = meta.get('pt2', None)
        if None in (pt1, pt2):
            self.hide_line()
        else:
            self.set_pts(pg.QtCore.QPointF(*pt1), pg.QtCore.QPointF(*pt2))


if __name__ == '__main__':
    import os, sys

    app = pg.mkQApp()

    meta_file = sys.argv[1]
    img_files = sys.argv[2:]
    win = MainWindow(meta_file, img_files)
    win.resize(1000, 800)
    win.show()

    if sys.flags.interactive == 0:
        app.exec_()