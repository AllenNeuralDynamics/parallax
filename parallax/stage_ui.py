from PyQt5.QtWidgets import QWidget

class StageUI(QWidget):
    def __init__(self, model, parent=None):
        QWidget.__init__(self, parent)
        self.model = model
        self.ui = parent
        self.update_stage_selector()
    
    def update_stage_selector(self):
        self.ui.stage_selector.clear()
        # Then, add the new items
        for stage in self.model.stages.keys():
            self.ui.stage_selector.addItem(stage)
            
        