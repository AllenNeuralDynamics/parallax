# tests/test_base_camera.py
import datetime
import numpy as np
import pytest

from parallax.cameras.camera_base_binding import BaseCamera


def test_basecamera_is_abstract():
    # Abstract methods should prevent direct instantiation
    with pytest.raises(TypeError):
        BaseCamera()


class DummyCamera(BaseCamera):
    """
    Minimal concrete implementation to exercise BaseCamera behavior.
    """

    def __init__(self, ts: float):
        # Provide an attribute used by BaseCamera.get_last_capture_time()
        self.last_capture_time = ts
        self._stopped = False
        self._saved = []

    def name(self, sn_only: bool = False) -> str:
        return "DummySN" if sn_only else "DummyCam (SN DummySN)"

    def get_last_image_data(self) -> np.ndarray:
        return np.zeros((10, 10, 3), dtype=np.uint8)

    # Override a few no-ops to prove they’re overridable (no side effects required)
    def stop(self, clean: bool = False) -> None:
        self._stopped = True

    def save_last_image(self, filepath: str, isTimestamp: bool = False, custom_name: str = "Camera_") -> None:
        # Record the intent; no disk I/O in unit tests
        self._saved.append((filepath, isTimestamp, custom_name))

    def begin_continuous_acquisition(self) -> None:
        pass

    def set_wb(self, channel: str, wb: float = 1.2) -> None:
        pass

    def set_gamma(self, gamma: float = 1.0) -> None:
        pass

    def set_gain(self, gain: int = 10) -> None:
        pass

    def set_exposure(self, expTime: int = 16000) -> None:
        pass


@pytest.mark.parametrize(
    "ts",
    [
        1704067200.0,  # 2024-01-01 00:00:00 local time (may differ by TZ, but we compare consistently)
        1719792000.123456,  # mid-2024 with fractional seconds
    ],
)
def test_get_last_capture_time_formats(ts):
    cam = DummyCamera(ts)

    # Build expected strings using the same local-time logic to avoid TZ flakiness
    dt = datetime.datetime.fromtimestamp(ts)
    expected_no_ms = f"{dt:%Y%m%d-%H%M%S}"
    expected_ms = f"{dt:%Y%m%d-%H%M%S}.{dt.microsecond // 1000:03d}"

    assert cam.get_last_capture_time(millisecond=False) == expected_no_ms
    assert cam.get_last_capture_time(millisecond=True) == expected_ms


def test_default_getters_return_sentinels():
    cam = DummyCamera(1704067200.0)
    # BaseCamera defaults
    assert cam.get_wb("Red") == -1.0
    assert cam.get_gain() == -1
    assert cam.get_exposure() == -1


def test_name_and_image_data_and_overrides():
    cam = DummyCamera(1704067200.0)

    # name()
    assert "DummyCam" in cam.name(sn_only=False)
    assert cam.name(sn_only=True) == "DummySN"

    # get_last_image_data()
    arr = cam.get_last_image_data()
    assert isinstance(arr, np.ndarray)
    assert arr.shape == (10, 10, 3)

    # stop() override sets a flag
    assert not cam._stopped
    cam.stop(clean=True)
    assert cam._stopped is True

    # save_last_image() override records call without filesystem I/O
    assert cam._saved == []
    cam.save_last_image("/tmp", isTimestamp=True, custom_name="Test_")
    assert cam._saved == [("/tmp", True, "Test_")]
