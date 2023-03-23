from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit

import time, datetime

class MessageLog(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent=parent)

        self.message_log = QTextEdit()
        self.vbar = self.message_log.verticalScrollBar()

        self.message_log.setReadOnly(True)
        self.message_log.objectName = 'Messages'

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.message_log)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(main_layout)

    def post(self, message, **kwargs):
        dt = datetime.datetime.fromtimestamp(time.time())
        prefix = '<b>[%02d:%02d:%02d]</b> ' % (dt.hour, dt.minute, dt.second)
        # handle multi-line messages
        split_messages = str(message).splitlines()
        self.message_log.append(prefix + split_messages.pop(0))
        while split_messages != []:
            self.message_log.append(split_messages.pop(0))
        self.vbar.setValue(self.vbar.maximum())
