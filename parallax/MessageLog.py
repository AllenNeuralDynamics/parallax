from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit

import time, datetime

class MessageLog(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent=parent)

        self.messageLog = QTextEdit()
        self.vbar = self.messageLog.verticalScrollBar()

        self.messageLog.setReadOnly(True)
        self.messageLog.objectName = 'Messages'

        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.messageLog)
        self.setLayout(mainLayout)

    def post(self, message, **kwargs):
        dt = datetime.datetime.fromtimestamp(time.time())
        prefix = '<b>[%02d:%02d:%02d]</b> ' % (dt.hour, dt.minute, dt.second)
        # handle multi-line messages
        split_messages = str(message).splitlines()
        self.messageLog.append(prefix + split_messages.pop(0))
        while split_messages != []:
            self.messageLog.append(split_messages.pop(0))
        self.vbar.setValue(self.vbar.maximum())
