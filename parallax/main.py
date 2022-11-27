from PyQt5.QtWidgets import QApplication
import os

from .model import Model
from .main_window import MainWindow

# allow multiple OpenMP instances
os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'

# change workdir to src/
os.chdir(os.path.dirname(os.path.realpath(__file__)))

if __name__ == '__main__':
    app = QApplication([])
    model = Model()
    main_window = MainWindow(model)
    main_window.show()

    main_window.assign_cameras()

    app.exec()
    model.clean()
