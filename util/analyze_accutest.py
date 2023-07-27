#!/usr/bin/python3

import numpy as np
import pyqtgraph as pg
import argparse

# parse args
parser = argparse.ArgumentParser(prog='analyze_accutest.py',
                            description='print the statistics from a Parallax accuracy test\n'
                                        'plot the histograms')
parser.add_argument('filename', help='the filename of the accutest file (.npy)')

args = parser.parse_args()


data = np.load(args.filename)

# calculate stats
npts = data.shape[0]
coords_stage = data[:,:3]
coords_recon = data[:,3:]
delta = coords_recon - coords_stage
dx = delta[:,0]
dy = delta[:,1]
dz = delta[:,2]
ds = np.sqrt(dx**2 + dy**2 + dz**2)
rmse = np.sqrt(np.mean(dx**2) + np.mean(dy**2) + np.mean(dz**2))
extremeVal = np.abs(np.concatenate((dx,dy,dz))).max()

# text output
print('mean, std dx: ', np.mean(dx), np.std(dx))
print('mean, std dy: ', np.mean(dy), np.std(dy))
print('mean, std dz: ', np.mean(dz), np.std(dz))
print('mean, std ds: ', np.mean(ds), np.std(ds))
print('rmse: ', rmse)

# plotting

histo_widget = pg.GraphicsLayoutWidget()
pi_x = histo_widget.addPlot(row=0, col=0)
pi_x.setLabel('bottom', 'dx (um)')
pi_y = histo_widget.addPlot(row=0, col=1)
pi_y.setLabel('bottom', 'dy (um)')
pi_z = histo_widget.addPlot(row=0, col=2)
pi_z.setLabel('bottom', 'dz (um)')
xhist, xbins = np.histogram(dx, bins=20)
yhist, ybins = np.histogram(dy, bins=20)
zhist, zbins = np.histogram(dz, bins=20)
shist, sbins = np.histogram(ds, bins=20)
bargraph_x = pg.BarGraphItem(x0=xbins[:-1], x1=xbins[1:], height=xhist, brush ='r')
bargraph_y = pg.BarGraphItem(x0=ybins[:-1], x1=ybins[1:], height=yhist, brush ='g')
bargraph_z = pg.BarGraphItem(x0=zbins[:-1], x1=zbins[1:], height=zhist, brush ='b')
bargraph_s = pg.BarGraphItem(x0=zbins[:-1], x1=sbins[1:], height=shist, brush ='y')
for i,bg in enumerate([bargraph_x, bargraph_y, bargraph_z]):
    pi = histo_widget.getItem(0,i)
    pi.setXRange((-1)*extremeVal, extremeVal)
    pi.addItem(bg)

histo_widget.show()

pg.QtWidgets.QApplication.exec_()
