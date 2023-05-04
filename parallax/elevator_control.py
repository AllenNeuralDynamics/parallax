#!/usr/bin/env python

from PyQt5.QtWidgets import QWidget, QPushButton, QLabel, QComboBox, QLineEdit
from PyQt5.QtWidgets import QVBoxLayout, QGridLayout, QTabWidget
from PyQt5.QtWidgets import QListWidget, QListWidgetItem, QMenu, QFileDialog
from PyQt5.QtWidgets import QDialog, QLineEdit, QDialogButtonBox, QInputDialog
from PyQt5.QtWidgets import QAbstractItemView
from PyQt5.QtGui import QIcon, QContextMenuEvent
from PyQt5.QtCore import Qt, QEvent, pyqtSignal, QTimer

import time
import datetime
import os
import pickle

from . import get_image_file, data_dir

class SetpointDialog(QDialog):

    def __init__(self, name=None, pos=None, edit_name=True):
        QDialog.__init__(self)

        self.name_label = QLabel('Name:')
        self.name_edit = QLineEdit()
        if name:
            self.name_edit.setText(name)
        self.name_edit.setFocus()
        self.name_edit.setEnabled(edit_name)

        self.pos_label = QLabel('Position (mm):')
        self.pos_edit = QLineEdit()
        if pos:
            self.pos_edit.setText(str(pos * 1e3))

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        layout = QGridLayout()
        layout.addWidget(self.name_label, 0,0, 1,1)
        layout.addWidget(self.name_edit, 0,1, 1,1)
        layout.addWidget(self.pos_label, 1,0, 1,1)
        layout.addWidget(self.pos_edit, 1,1, 1,1)
        layout.addWidget(self.buttons, 2,0, 1, 2)
        
        self.setLayout(layout)
        self.setFocusProxy(self.name_edit)

    def get_name(self):
        return self.name_edit.text()

    def get_pos(self):
        return float(self.pos_edit.text()) / 1e3


class SetpointItem(QListWidgetItem):

    def __init__(self, name, pos):
        QListWidgetItem.__init__(self)
        self.name = name
        self.pos = pos
        self.update_text()

    def set_name(self, name):
        self.name = name
        self.update_text()

    def set_pos(self, pos):
        self.pos = pos
        self.update_text()

    def update_text(self):
        self.setText('%s [position (mm) = %.1f]' % (self.name, self.pos * 1e3))


class FirmwareSetpointsTab(QWidget):

    msg_posted = pyqtSignal(str)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent=parent)

        self.list_widget = QListWidget()
        self.list_widget.installEventFilter(self)

        self.add_button = QPushButton('Go to selected')
        self.add_button.clicked.connect(self.go)

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.list_widget)
        self.layout.addWidget(self.add_button)
        self.setLayout(self.layout)

        self.elevator = None

    def set_elevator(self, elevator):
        self.elevator = elevator
        self.update_list()

    def update_list(self):
        self.clear()
        for num in range(1,17):
            pos = self.elevator.get_firmware_setpoint(num)
            item = SetpointItem('FW#%d' % num, pos) 
            self.list_widget.addItem(item)

    def clear(self):
        self.list_widget.clear()

    def go(self):
        if self.elevator is not None:
            setpoints = self.list_widget.selectedItems()
            if setpoints:
                setpoint = setpoints[0]
                pos = setpoint.pos
                self.elevator.move_absolute(pos)

    def grab_setpoint(self):
        pos = self.elevator.get_position()
        num = self.list_widget.indexFromItem(self.item_selected).row() + 1
        self.elevator.set_firmware_setpoint(num, pos)
        self.update_list()

    def edit_setpoint(self):
        name = self.item_selected.name
        pos = self.item_selected.pos
        num = self.list_widget.indexFromItem(self.item_selected).row() + 1
        dlg = SetpointDialog(name, pos, edit_name=False)
        if dlg.exec_():
            pos = dlg.get_pos()
            self.elevator.set_firmware_setpoint(num, pos)
            self.update_list()

    def reset_setpoint(self):
        num = self.list_widget.indexFromItem(self.item_selected).row() + 1
        self.elevator.set_firmware_setpoint(num, 0)
        self.update_list()

    def eventFilter(self, src, e):
        if (src is self.list_widget) and (e.type() == QEvent.ContextMenu):
            self.item_selected = src.itemAt(e.pos())
            if self.item_selected:
                menu = QMenu()
                edit_action = menu.addAction('Edit')
                edit_action.triggered.connect(self.edit_setpoint)
                grab_action = menu.addAction('Grab Current Location')
                grab_action.triggered.connect(self.grab_setpoint)
                reset_action = menu.addAction('Reset')
                reset_action.triggered.connect(self.reset_setpoint)
                menu.exec_(e.globalPos())
            return True
        return super().eventFilter(src, e)


class SoftwareSetpointsTab(QWidget):

    msg_posted = pyqtSignal(str)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent=parent)

        self.list_widget = QListWidget()
        self.list_widget.installEventFilter(self)
        self.list_widget.setDragDropMode(QAbstractItemView.InternalMove)

        self.go_button = QPushButton('Go to selected')
        self.go_button.clicked.connect(self.go)

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.list_widget)
        self.layout.addWidget(self.go_button)
        self.setLayout(self.layout)

        self.elevator = None

    def set_elevator(self, elevator):
        self.elevator = elevator

    def go(self):
        if self.elevator is not None:
            setpoints = self.list_widget.selectedItems()
            if setpoints:
                setpoint = setpoints[0]
                pos = setpoint.pos
                self.elevator.move_absolute(pos)

    def add_setpoint(self):
        dlg = SetpointDialog()
        if dlg.exec_():
            name = dlg.get_name()
            pos = dlg.get_pos()
            item = SetpointItem(name, pos)
            self.list_widget.addItem(item)

    def grab_setpoint(self):
        pos = self.elevator.get_position()
        dlg = SetpointDialog(pos=pos)
        if dlg.exec_():
            name = dlg.get_name()
            pos = dlg.get_pos()
            item = SetpointItem(name, pos)
            self.list_widget.addItem(item)

    def delete_setpoint(self):
        i = self.list_widget.row(self.item_selected)
        self.list_widget.takeItem(i)
        del self.item_selected
        self.item_selected = None

    def edit_setpoint(self):
        name = self.item_selected.name
        pos = self.item_selected.pos
        dlg = SetpointDialog(name, pos)
        if dlg.exec_():
            name = dlg.get_name()
            pos = dlg.get_pos()
            self.item_selected.set_name(name)
            self.item_selected.set_pos(pos)

    def eventFilter(self, src, e):
        if (src is self.list_widget) and (e.type() == QEvent.ContextMenu):
            self.item_selected = src.itemAt(e.pos())
            if self.item_selected:
                menu = QMenu()
                edit_action = menu.addAction('Edit')
                edit_action.triggered.connect(self.edit_setpoint)
                delete_action = menu.addAction('Delete')
                delete_action.triggered.connect(self.delete_setpoint)
                menu.exec_(e.globalPos())
            else:
                menu = QMenu()
                add_setpoint_menu = QMenu('Add setpoint', menu)
                grab_action = add_setpoint_menu.addAction('Grab current location')
                grab_action.triggered.connect(self.grab_setpoint)
                grab_action.setEnabled(self.elevator is not None)
                add_action = add_setpoint_menu.addAction('Add manually')
                add_action.triggered.connect(self.add_setpoint)
                menu.addMenu(add_setpoint_menu)
                load_action = menu.addAction('Load from file')
                load_action.triggered.connect(self.load)
                save_action = menu.addAction('Save to file')
                save_action.triggered.connect(self.save)
                clear_action = menu.addAction('Clear items')
                clear_action.triggered.connect(self.clear)
                menu.exec_(e.globalPos())
            return True
        return super().eventFilter(src, e)

    def load(self):
        filename = QFileDialog.getOpenFileName(self, 'Load setpoints file',
                                        data_dir, 'Pickle files (*.pkl)')[0]
        if filename:
            with open(filename, 'rb') as f:
                setpoints = pickle.load(f)
                for sp in setpoints:
                    name, pos = sp
                    self.list_widget.addItem(SetpointItem(name, pos))
        
    def save(self):
        setpoints = []
        for i in range(self.list_widget.count()):
            sp = self.list_widget.item(i)
            name = sp.name
            pos = sp.pos
            setpoints.append((name, pos))
        
        ts = time.time()
        dt = datetime.datetime.fromtimestamp(ts)
        suggested_basename = 'setpoints_%04d%02d%02d-%02d%02d%02d.pkl' % (dt.year,
                                        dt.month, dt.day, dt.hour, dt.minute, dt.second)
        suggested_filename = os.path.join(data_dir, suggested_basename)
        filename = QFileDialog.getSaveFileName(self, 'Save setpoints',
                                                suggested_filename,
                                                'Pickle files (*.pkl)')[0]
        if filename:
            with open(filename, 'wb') as f:
                pickle.dump(setpoints, f)
            self.msg_posted.emit('Saved setpoints to: %s' % (filename))

    def clear(self):
        self.list_widget.clear()
        


class AdvancedTab(QWidget):

    msg_posted = pyqtSignal(str)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent=parent)

        self.speed_button = QPushButton('Speed')
        self.speed_button.clicked.connect(self.set_speed)

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.speed_button)
        self.setLayout(self.layout)
        
        self.set_elevator(None)

    def set_elevator(self, elevator):
        self.elevator = elevator
        self.update_gui()
        
    def update_gui(self):
        enable = self.elevator is not None
        self.speed_button.setEnabled(enable)
        if self.elevator:
            speed = self.elevator.get_speed()
            self.speed_button.setText('Speed = %.2f' % speed)

    def move_up(self):
        if self.elevator is not None:
            self.elevator.move_relative(10000)

    def move_down(self):
        if self.elevator is not None:
            self.elevator.move_relative(-10000)

    def set_speed(self):
        speed, ok = QInputDialog.getDouble(self, 'Set Speed', 'Speed')
        if ok:
            self.elevator.set_speed(speed)
            self.update_gui()


class ElevatorControlTool(QWidget):

    msg_posted = pyqtSignal(str)

    def __init__(self, model):
        QWidget.__init__(self, parent=None)
        self.model = model

        self.elevator = None

        self.select_elevator_label = QLabel('Select elevator:')
        self.dropdown = QComboBox()

        self.fw_setpoints_tab = FirmwareSetpointsTab(parent=self)
        self.fw_setpoints_tab.msg_posted.connect(self.msg_posted)
        self.sw_setpoints_tab = SoftwareSetpointsTab(parent=self)
        self.sw_setpoints_tab.msg_posted.connect(self.msg_posted)
        self.advanced_tab = AdvancedTab(parent=self)
        self.advanced_tab.msg_posted.connect(self.msg_posted)

        self.dropdown.currentTextChanged.connect(self.handleSelection)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.fw_setpoints_tab, 'Firmware Setpoints')
        self.tabs.addTab(self.sw_setpoints_tab, 'Software Setpoints')
        self.tabs.addTab(self.advanced_tab, 'Advanced')

        self.pos_label = QLabel()
        self.pos_label.setAlignment(Qt.AlignCenter)

        self.twist_label = QLabel()
        self.twist_label.setAlignment(Qt.AlignCenter)

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.select_elevator_label)
        self.layout.addWidget(self.dropdown)
        self.layout.addWidget(self.tabs)
        self.layout.addWidget(self.pos_label)
        self.layout.addWidget(self.twist_label)
        self.setLayout(self.layout)

        self.setWindowTitle('Elevator Control Tool')
        self.setWindowIcon(QIcon(get_image_file('sextant.png')))
        self.setMinimumWidth(450)

        self.populate_dropdown()

        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.update_gui)
        self.refresh_timer.start(500)

    def populate_dropdown(self):
        for name in self.model.elevators.keys():
            self.dropdown.addItem(name)

    def handleSelection(self, name):
        self.elevator = self.model.elevators[name]
        self.fw_setpoints_tab.set_elevator(self.elevator)
        self.sw_setpoints_tab.set_elevator(self.elevator)
        self.advanced_tab.set_elevator(self.elevator)
        self.update_gui()

    def update_gui(self):
        if self.elevator is not None:
            pos = self.elevator.get_position()
            self.pos_label.setText('Current Position (mm): %.1f' % (pos * 1e3))
            twist = self.elevator.get_twist()
            self.twist_label.setText('Current Twist (um): %.1f' % (twist * 1e6))

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            if self.elevator:
                self.elevator.halt()

