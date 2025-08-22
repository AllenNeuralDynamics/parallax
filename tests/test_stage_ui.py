# tests/test_stage_ui.py
import pytest
from PyQt5.QtWidgets import QWidget, QComboBox, QLabel, QLineEdit, QVBoxLayout
from unittest.mock import Mock

from parallax.stages.stage_ui import StageUI


# ---------- Minimal stage/model stubs ----------

class _StageObj:
    def __init__(self, sn="SN001",
                 lx=1.0, ly=2.0, lz=3.0,
                 gx=100.0, gy=200.0, gz=300.0):
        self.sn = sn
        self.stage_x = lx
        self.stage_y = ly
        self.stage_z = lz
        self.stage_x_global = gx
        self.stage_y_global = gy
        self.stage_z_global = gz


class _ModelStub:
    def __init__(self):
        self.reticle_detection_status = "default"
        self._stage_obj = _StageObj()
        # StageUI.update_stage_selector() iterates keys of model.stages,
        # and updateStageSN() expects dict with 'obj'
        self.stages = {"stage1": {"obj": self._stage_obj}}

    def get_stage(self, stage_id):
        entry = self.stages.get(stage_id)
        return entry["obj"] if entry else None


# ---------- Parent control panel stub ----------

class _ParentWithModel(QWidget):
    """
    Mimics the control panel object StageUI expects:
    - .model
    - .stage_selector (QComboBox with .currentIndexChanged)
    - .reticle_selector (QComboBox)
    - .stage_sn (QLabel-ish with setText)
    - .local_coords_x/y/z (QLineEdit-ish with setText)
    - .global_coords_x/y/z (QLineEdit-ish with setText)
    """
    def __init__(self, model):
        super().__init__()
        self.model = model

        lay = QVBoxLayout(self)

        self.stage_selector = QComboBox(self)
        lay.addWidget(self.stage_selector)

        self.reticle_selector = QComboBox(self)
        # include both “Proj” and normal variants
        self.reticle_selector.addItems(["Global coords", "Proj Global coords", "Global coords (A)"])
        self.reticle_selector.setCurrentIndex(0)
        lay.addWidget(self.reticle_selector)

        self.stage_sn = QLabel(self)
        lay.addWidget(self.stage_sn)

        # Local coords
        self.local_coords_x = QLineEdit(self); lay.addWidget(self.local_coords_x)
        self.local_coords_y = QLineEdit(self); lay.addWidget(self.local_coords_y)
        self.local_coords_z = QLineEdit(self); lay.addWidget(self.local_coords_z)

        # Global coords
        self.global_coords_x = QLineEdit(self); lay.addWidget(self.global_coords_x)
        self.global_coords_y = QLineEdit(self); lay.addWidget(self.global_coords_y)
        self.global_coords_z = QLineEdit(self); lay.addWidget(self.global_coords_z)


# ---------- Reticle metadata stub (optional) ----------

class _ReticleMetaStub:
    def __init__(self, dx=10.0, dy=0.0, dz=5.0):
        self.dx, self.dy, self.dz = dx, dy, dz

    def get_global_coords_with_offset(self, name, global_pts):
        x, y, z = list(global_pts)
        return x + self.dx, y + self.dy, z + self.dz


# ---------- Builders ----------

def _build_stage_ui(qtbot, model=None, with_meta=False):
    m = model or _ModelStub()
    parent = _ParentWithModel(m)
    qtbot.addWidget(parent)  # ensure lifetime managed by pytest-qt
    meta = _ReticleMetaStub() if with_meta else None
    ui = StageUI(parent, meta)
    qtbot.addWidget(ui)
    return ui, parent, m


# ---------- Tests ----------

def test_initialization(qtbot):
    ui, parent, model = _build_stage_ui(qtbot)
    # Stage selector should have been populated with one item data "stage1"
    assert parent.stage_selector.count() == 1
    assert ui.get_current_stage_id() == "stage1"
    # SN label updated
    assert parent.stage_sn.text().strip() == model._stage_obj.sn
    # Local coords populated
    assert parent.local_coords_x.text() == str(model._stage_obj.stage_x)
    assert parent.local_coords_y.text() == str(model._stage_obj.stage_y)
    assert parent.local_coords_z.text() == str(model._stage_obj.stage_z)
    # Global coords populated
    assert parent.global_coords_x.text() == str(model._stage_obj.stage_x_global)
    assert parent.global_coords_y.text() == str(model._stage_obj.stage_y_global)
    assert parent.global_coords_z.text() == str(model._stage_obj.stage_z_global)


def test_stage_switch_signal(qtbot):
    ui, parent, model = _build_stage_ui(qtbot)
    # add a second stage and repopulate selector
    model.stages["stage2"] = {"obj": _StageObj(sn="SN002", gx=111, gy=222, gz=333)}
    ui.initialize()  # refresh selector/items

    # spy on the StageUI signal
    got = []
    ui.prev_curr_stages.connect(lambda prev, curr: got.append((prev, curr)))

    # switch index -> should emit (prev='stage1', curr='stage2')
    parent.stage_selector.setCurrentIndex(1)
    # force sendInfoToStageWidget via signal connection
    # (already connected in initialize via stage_selector_activate_actions)

    # basic assertion
    assert got and got[-1] == ("stage1", "stage2")


def test_refresh_updates_fields_on_stage_change(qtbot):
    ui, parent, model = _build_stage_ui(qtbot)
    model.stages["stage2"] = {"obj": _StageObj(sn="SN002", lx=9, ly=8, lz=7, gx=1, gy=2, gz=3)}
    ui.initialize()

    parent.stage_selector.setCurrentIndex(1)

    assert parent.stage_sn.text().strip() == "SN002"
    assert parent.local_coords_x.text() == "9"
    assert parent.local_coords_y.text() == "8"
    assert parent.local_coords_z.text() == "7"
    assert parent.global_coords_x.text() == "1"
    assert parent.global_coords_y.text() == "2"
    assert parent.global_coords_z.text() == "3"


def test_reticle_proj_sets_default_coords(qtbot):
    ui, parent, model = _build_stage_ui(qtbot)
    # choose “Proj Global coords”
    idx = parent.reticle_selector.findText("Proj Global coords")
    parent.reticle_selector.setCurrentIndex(idx)
    # trigger handler
    ui.updateCurrentReticle()

    assert parent.global_coords_x.text() == "-"
    assert parent.global_coords_y.text() == "-"
    assert parent.global_coords_z.text() == "-"


def test_reticle_with_offset_applies_metadata(qtbot):
    ui, parent, model = _build_stage_ui(qtbot, with_meta=True)
    # pick "Global coords (A)" so StageUI extracts 'A' and applies metadata
    idx = parent.reticle_selector.findText("Global coords (A)")
    parent.reticle_selector.setCurrentIndex(idx)
    ui.updateCurrentReticle()

    # base globals are (100, 200, 300); metadata adds (+10, +0, +5)
    assert parent.global_coords_x.text() == "110.0"
    assert parent.global_coords_y.text() == "200.0"
    assert parent.global_coords_z.text() == "305.0"
