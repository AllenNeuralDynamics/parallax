from PyQt4 import QtCore, QtGui
import sys, os, h5py, subprocess
import numpy as np
import hwif
from willowephys import WillowDataset
import config

"""
class MissingTargetError(Exception):

    def __init__(self, targetDir):
        Exception.__init__(self)
        self.targetDir = targetDir
"""

class ScanThread(QtCore.QThread):

    msgPosted = QtCore.pyqtSignal(str)
    finished = QtCore.pyqtSignal(object)

    def __init__(self, params):
        QtCore.QThread.__init__(self)
        self.params = params

        self.nsamples_requested = params['nsamples']
        self.filename = params['filename']
        self.isTerminated = False

    def handleCancel(self):
        """
        This is required to prevent the race condition between QProgressDialog
        and this thread. self.isTerminated is checked before emission of valueChanged.
        """
        self.isTerminated = True
        self.terminate()

    def run(self):
        try:
            targetDir = os.path.dirname(self.filename)
            if not os.path.exists(targetDir):
                raise MissingTargetError(targetDir) 
            nsamples_actual = hwif.takeSnapshot(nsamples=self.nsamples_requested, filename=self.filename)
            self.msgPosted.emit('Snapshot Complete: %d samples saved to %s' %
                (nsamples_actual, self.filename))
        except hwif.StateChangeError as e:
            self.msgPosted.emit('StateChangeError: %s' % e.message)
        except hwif.hwifError as e:
            self.msgPosted.emit(e.message)
        except MissingTargetError as e:
            self.msgPosted.emit('Error: Target directory %s does not exist' % e.targetDir)
        finally:
            self.finished.emit(self.params)
