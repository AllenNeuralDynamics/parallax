from PyQt5.QtWidgets import QComboBox
from PyQt5.QtCore import Qt


class StageDropdown(QComboBox):

    def __init__(self, model):
        QComboBox.__init__(self)
        self.model = model
        self.stages = []

        self.selected = False
        self.setFocusPolicy(Qt.NoFocus)
        self.activated.connect(self.set_selected)

    def set_selected(self):
        self.selected = True

    def is_selected(self):
        return self.selected

    def current_stage(self):
        return self.stages[self.currentIndex()]

    def showPopup(self):
        self.populate()
        QComboBox.showPopup(self)

    def populate(self):
        self.clear()
        self.stages = self.model.stages[:] 
        for stage in self.stages:
            self.addItem(stage.get_name())


