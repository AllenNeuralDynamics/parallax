from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QPushButton

class ZaberTab(QWidget):

    def __init__(self, msgLog):
        QWidget.__init__(self)

        self.msgLog = msgLog

        self.raiseButton = QPushButton('Raise Heavy Mechanics')
        self.raiseButton.clicked.connect(self.raiseZaber)
        self.lowerButton = QPushButton('Lower Heavy Mechanics')
        self.lowerButton.clicked.connect(self.lowerZaber)

        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.raiseButton)
        mainLayout.addWidget(self.lowerButton)
        self.setLayout(mainLayout)

    def raiseZaber(self):
        pass    # TODO

    def lowerZaber(self):
        pass    # TODO
