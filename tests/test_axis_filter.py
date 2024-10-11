import pytest
import numpy as np
import time
from PyQt5.QtCore import QCoreApplication, QEventLoop
from unittest.mock import Mock
from parallax.axis_filter import AxisFilter

@pytest.fixture
def reticle_coords():
    """Mock reticle coordinates for testing."""
    return [
        np.array([[1819, 1680], [1872, 1672], [1925, 1663], [1976, 1655], [2029, 1646],
                  [2081, 1638], [2132, 1630], [2184, 1621], [2236, 1613], [2287, 1604],
                  [2339, 1596], [2390, 1588], [2441, 1579], [2492, 1571], [2543, 1563],
                  [2594, 1555], [2644, 1546], [2696, 1538], [2746, 1530], [2796, 1522],
                  [2846, 1514]]), 
        np.array([[2491, 2084], [2476, 2035], [2460, 1985], [2445, 1936], [2429, 1887],
                  [2414, 1838], [2399, 1789], [2384, 1741], [2369, 1693], [2354, 1644],
                  [2339, 1596], [2324, 1548], [2308, 1500], [2293, 1452], [2278, 1404],
                  [2264, 1357], [2249, 1310], [2234, 1262], [2219, 1215], [2205, 1168],
                  [2190, 1121]])
    ]

@pytest.fixture
def mock_model(reticle_coords):
    """Mock the model to return predefined reticle coordinates and other properties."""
    model = Mock()
    model.get_coords_axis.return_value = reticle_coords
    model.get_pos_x.return_value = (200, 200)  # Simulate a previously stored pos_x
    return model

@pytest.fixture
def test_frame():
    """Create a test frame for processing."""
    return np.random.randint(0, 256, (3000, 4000, 3), dtype=np.uint8)

@pytest.fixture
def axis_filter(mock_model):
    """Initialize the AxisFilter with the mocked model."""
    return AxisFilter(mock_model, "TestCamera123")

@pytest.fixture(scope='module', autouse=True)
def qt_application():
    """Set up the QCoreApplication for the PyQt event loop."""
    app = QCoreApplication([])  # Necessary for PyQt signal-slot mechanism
    yield app

# Helper function to process and test pos_x
def process_axis_filter(axis_filter, test_frame, click_position, qt_application, expected_pos_x):
    """Helper function to process frame and simulate a user click."""
    axis_filter.start()
    axis_filter.process(test_frame)

    # Simulate user click
    axis_filter.clicked_position(click_position)

    # Allow event loop to process
    loop = QEventLoop()
    for _ in range(10):
        qt_application.processEvents()
        time.sleep(0.1)

    # Check that pos_x is updated
    assert axis_filter.worker.pos_x == expected_pos_x, f"pos_x was not set correctly for click {click_position}"

    # Cleanup after each case
    axis_filter.stop()
    axis_filter.clean()

# Test the process of handling reticle coordinates and checking pos_x for 4 different click cases
def test_axis_filter_pos_x_cases(axis_filter, test_frame, qt_application):
    """Test AxisFilter's ability to detect and set pos_x based on user clicks near different reticle points."""

    # Test Case 1: Click near the first point of reticle_coords[0]
    process_axis_filter(axis_filter, test_frame, (1830, 1580), qt_application, (1819, 1680))

    # Reinitialize the AxisFilter for next test case
    axis_filter = AxisFilter(axis_filter.model, "TestCamera123")

    # Test Case 2: Click near the last point of reticle_coords[0]
    process_axis_filter(axis_filter, test_frame, (2857, 1594), qt_application, (2846, 1514))

    # Reinitialize the AxisFilter for next test case
    axis_filter = AxisFilter(axis_filter.model, "TestCamera123")

    # Test Case 3: Click near the first point of reticle_coords[1]
    process_axis_filter(axis_filter, test_frame, (2401, 2004), qt_application, (2491, 2084))

    # Reinitialize the AxisFilter for next test case
    axis_filter = AxisFilter(axis_filter.model, "TestCamera123")

    # Test Case 4: Click near the last point of reticle_coords[1]
    process_axis_filter(axis_filter, test_frame, (2290, 1221), qt_application, (2190, 1121))
