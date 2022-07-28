from PyQt5.QtWidgets import QComboBox
from PyQt5.QtCore import Qt

class StageDropdown(QComboBox):

    def __init__(self, model):
        QComboBox.__init__(self)
        self.model = model
        self.setFocusPolicy(Qt.NoFocus)

    def showPopup(self):
        self.populate()
        QComboBox.showPopup(self)

    def populate(self):
        self.clear()
        for ip in self.model.stages.keys():
            self.addItem(ip)


