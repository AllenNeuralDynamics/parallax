import pytest
import numpy as np
from parallax.reticle_detection.reticle_detection_coords_interests import ReticleDetectCoordsInterest

@pytest.fixture
def coords_interest_detector():
    """
    Fixture for creating an instance of ReticleDetectCoordsInterest.
    """
    return ReticleDetectCoordsInterest()

@pytest.fixture
def sample_pixels_in_lines():
    """
    Fixture to provide sample pixel lines for testing.
    """
    return [
        np.array([
            [473, 1900], [529, 1891], [584, 1882], [639, 1873], [694, 1864], [749, 1855],
            [804, 1846], [858, 1837], [913, 1828], [967, 1820], [1021, 1811], [1075, 1802],
            [1129, 1793], [1183, 1784], [1236, 1776], [1290, 1767], [1343, 1758], [1397, 1750],
            [1450, 1741], [1503, 1732], [1556, 1724], [1609, 1715], [1662, 1707], [1715, 1698],
            [1767, 1689], [1820, 1681], [1872, 1672], [1924, 1664], [1976, 1655], [2028, 1647],
            [2080, 1639], [2132, 1630], [2184, 1622], [2235, 1613], [2287, 1605], [2338, 1597],
            [2389, 1588], [2441, 1580], [2492, 1572], [2542, 1563], [2593, 1555], [2644, 1547],
            [2695, 1539], [2745, 1530], [2795, 1522], [2846, 1514], [2896, 1506], [2947, 1498],
            [2996, 1490], [3046, 1481], [3096, 1473], [3146, 1465], [3195, 1457], [3245, 1449]
        ]),
        np.array([
            [1961, 388], [1975, 433], [1989, 479], [2003, 524], [2017, 569], [2032, 615],
            [2046, 660], [2060, 706], [2074, 751], [2089, 797], [2103, 843], [2117, 889],
            [2132, 936], [2146, 982], [2161, 1029], [2175, 1075], [2190, 1122], [2205, 1169],
            [2219, 1216], [2234, 1263], [2249, 1310], [2264, 1358], [2278, 1405], [2293, 1453],
            [2308, 1501], [2323, 1548], [2338, 1596], [2353, 1645], [2368, 1693], [2383, 1741],
            [2399, 1790], [2414, 1839], [2429, 1888], [2444, 1936], [2460, 1986], [2475, 2035],
            [2491, 2085], [2506, 2134], [2522, 2184], [2537, 2233], [2553, 2284], [2568, 2333],
            [2584, 2383], [2600, 2435], [2616, 2485], [2632, 2536], [2647, 2586], [2663, 2637],
            [2680, 2689]
        ])
    ]

def test_get_coords_interest(coords_interest_detector, sample_pixels_in_lines):
    """
    Test the get_coords_interest method.
    """
    ret, x_axis_coords, y_axis_coords = coords_interest_detector.get_coords_interest(sample_pixels_in_lines)
    
    # Assert that the method returns True indicating success
    assert ret, "Failed to get coordinates of interest"

    # Check the returned x_axis_coords and y_axis_coords
    assert x_axis_coords is not None, "X-axis coordinates should not be None"
    assert y_axis_coords is not None, "Y-axis coordinates should not be None"
    assert len(x_axis_coords) == 21, f"Expected 21 points for x_axis_coords, got {len(x_axis_coords)}"
    assert len(y_axis_coords) == 21, f"Expected 21 points for y_axis_coords, got {len(y_axis_coords)}"

    # Assert that the result is close to the expected values
    expected_x_axis_coords = np.array([
        [1820, 1681], [1872, 1672], [1924, 1664], [1976, 1655], [2028, 1647],
        [2080, 1639], [2132, 1630], [2184, 1622], [2235, 1613], [2287, 1605],
        [2338, 1597], [2389, 1588], [2441, 1580], [2492, 1572], [2542, 1563],
        [2593, 1555], [2644, 1547], [2695, 1539], [2745, 1530], [2795, 1522],
        [2846, 1514]
    ])
    expected_y_axis_coords = np.array([
        [2491, 2085], [2475, 2035], [2460, 1986], [2444, 1936], [2429, 1888],
        [2414, 1839], [2399, 1790], [2383, 1741], [2368, 1693], [2353, 1645],
        [2338, 1597], [2323, 1548], [2308, 1501], [2293, 1453], [2278, 1405],
        [2264, 1358], [2249, 1310], [2234, 1263], [2219, 1216], [2205, 1169],
        [2190, 1122]
    ])

    np.testing.assert_allclose(x_axis_coords[:len(expected_x_axis_coords)], expected_x_axis_coords, atol=5,
        err_msg="X-axis coordinates do not match expected values.")
    np.testing.assert_allclose(y_axis_coords[:len(expected_y_axis_coords)], expected_y_axis_coords, atol=5,
        err_msg="Y-axis coordinates do not match expected values.")
