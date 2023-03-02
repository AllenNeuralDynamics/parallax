#!/usr/bin/python3 -i

import numpy as np
import pyqtgraph as pg
import pyqtgraph.opengl as gl
import sys

if len(sys.argv) < 2:
    print('Usage: %s data.npy' % sys.argv[0])
    sys.exit(0)

filename = sys.argv[1]
data = np.load(filename)

npts = data.shape[0]

coords_stage = data[:,:3]
coords_recon = data[:,3:]
delta = coords_recon - coords_stage

dx = delta[:,0]
dy = delta[:,1]
dz = delta[:,2]
ds = np.sqrt(dx**2 + dy**2 + dz**2)

print('RMS x error is: ', np.sqrt(np.mean(dx**2)))
print('RMS y error is: ', np.sqrt(np.mean(dy**2)))
print('RMS z error is: ', np.sqrt(np.mean(dz**2)))
print('Mean linear error is: ', np.mean(ds))

# Histograms
xhist, xbins = np.histogram(dx,  bins=20)
yhist, ybins = np.histogram(dy,  bins=20)
zhist, zbins = np.histogram(dz,  bins=20)
shist, sbins = np.histogram(ds,  bins=20)

# Scatter Plots
cmap = pg.colormap.get('coolwarm', source='matplotlib')
cmap.pos = np.linspace(-100,100,33) # how to set different number of stops?
colors4_dx = cmap.map(dx)
colors4_dy = cmap.map(dy)
colors4_dz = cmap.map(dz)

if __name__ == '__main__':

    app = pg.mkQApp()

    # Histograms

    bargraph_x = pg.BarGraphItem(x0=xbins[:-1], x1=xbins[1:], height=xhist, brush ='r')
    bargraph_y = pg.BarGraphItem(x0=ybins[:-1], x1=ybins[1:], height=yhist, brush ='g')
    bargraph_z = pg.BarGraphItem(x0=zbins[:-1], x1=zbins[1:], height=zhist, brush ='b')

    window = pg.GraphicsLayoutWidget()
    pi_x = window.addPlot(row=0, col=0)
    pi_x.addItem(bargraph_x)
    pi_x.setLabel('bottom', 'dx (um)')
    pi_y = window.addPlot(row=0, col=1)
    pi_y.addItem(bargraph_y)
    pi_y.setLabel('bottom', 'dy (um)')
    pi_z = window.addPlot(row=0, col=2)
    pi_z.addItem(bargraph_z)
    pi_z.setLabel('bottom', 'dz (um)')

    window.show()

    # Scatter Plots

    coord = gl.GLAxisItem()
    coord.setSize(15000, 15000, 15000)

    view_x = gl.GLViewWidget()
    scatter_dx = gl.GLScatterPlotItem(pos=coords_stage, size=10, color=colors4_dx/255)
    view_x.addItem(coord)
    view_x.addItem(scatter_dx)

    view_y = gl.GLViewWidget()
    scatter_dy = gl.GLScatterPlotItem(pos=coords_stage, size=10, color=colors4_dy/255)
    view_y.addItem(coord)
    view_y.addItem(scatter_dy)

    view_z = gl.GLViewWidget()
    scatter_dz = gl.GLScatterPlotItem(pos=coords_stage, size=10, color=colors4_dz/255)
    view_z.addItem(coord)
    view_z.addItem(scatter_dx)

    win = pg.QtWidgets.QWidget()
    layout = pg.QtWidgets.QHBoxLayout()
    layout.addWidget(view_x)
    layout.addWidget(view_y)
    layout.addWidget(view_z)
    win.setLayout(layout)
    win.setFixedWidth(1600)
    win.setFixedHeight(500)
    win.show()

    app.exec()

