import pytest
import json
import time
from unittest.mock import Mock, patch
from parallax.stage_controller import StageController
import requests

@pytest.fixture(scope="function")
def mock_model():
    """Fixture to create a mock model object."""
    model = Mock()
    model.stage_listener_url = "http://localhost:8080/"
    return model

@pytest.fixture(scope="function")
def stage_controller(mock_model):
    """Fixture to create a StageController instance with a mock model."""
    return StageController(mock_model)

def is_hw_connected(stage_controller):
    """
    Check if the hardware is connected by sending a test request.
    If the request fails or the response format is incorrect, return False.
    """
    try:
        status = stage_controller._get_status()
        # Check for the presence of "ProbeArray" and ensure that "Probes" > 0.
        # Also, check that the "ProbeArray" has elements.
        if status and "ProbeArray" in status and status.get("Probes", 0) > 0 and len(status["ProbeArray"]) > 0:
            return True
        else:
            return False
    except requests.RequestException:
        return False

# Use `pytest.mark.skipif` to conditionally skip tests if no hardware is connected
@pytest.mark.skipif(
    not is_hw_connected(StageController(Mock(stage_listener_url="http://localhost:8080/"))),
    reason="No hardware connected or unexpected response format. Skipping hardware tests."
)
def test_get_probe_index(stage_controller):
    """Test the _get_probe_index method."""
    # Get actual status from the stage controller
    status = stage_controller._get_status()
    assert "ProbeArray" in status, "Expected 'ProbeArray' in status response."

    # Use the actual ProbeArray to verify index retrieval
    probe_serial_numbers = [probe["SerialNumber"] for probe in status["ProbeArray"]]

    if len(probe_serial_numbers) > 0:
        first_sn = probe_serial_numbers[0]
        print(f"First probe serial number: {first_sn}")
        assert stage_controller._get_probe_index(first_sn) == 0

        # If there are multiple probes, test another serial number
        if len(probe_serial_numbers) > 1:
            second_sn = probe_serial_numbers[1]
            assert stage_controller._get_probe_index(second_sn) == 1

    # Check that an unknown serial number returns None
    assert stage_controller._get_probe_index("UNKNOWN_SN") is None

@pytest.mark.skipif(
    not is_hw_connected(StageController(Mock(stage_listener_url="http://localhost:8080/"))),
    reason="No hardware connected or unexpected response format. Skipping hardware tests."
)
def test_move_request(stage_controller):
    """Test the request method of the StageController."""
    # Get the actual status from the stage controller
    status = stage_controller._get_status()
    assert "ProbeArray" in status, "Expected 'ProbeArray' in status response."

    # Get a valid serial number and current X, Y positions from the ProbeArray
    first_probe_sn = status["ProbeArray"][0]["SerialNumber"]
    current_x = status["ProbeArray"][0]["Stage_X"]
    current_y = status["ProbeArray"][0]["Stage_Y"]
    current_z = status["ProbeArray"][0]["Stage_Z"]
    print("probe_sn: ", first_probe_sn)
    print(f"Current X, Y, Z positions: {current_x}, {current_y}, {current_z}")

    # Calculate the new target positions
    target_x = current_x 
    target_y = current_y
    print(f"Target X, Y, Z positions: {target_x}, {target_y}, {15.0}")

    # Create a command for movement
    command = {
        "move_type": "moveXY",
        "stage_sn": first_probe_sn,
        "x": target_x*1000, # um
        "y": target_y*1000 # um
    }

    # Send the move request
    stage_controller.request(command)

    # Allow time for the movement to complete
    max_attempts = 10
    for attempt in range(max_attempts):
        time.sleep(0.5)  # Wait for 0.5 seconds between checks
        updated_status = stage_controller._get_status()
        updated_x = updated_status["ProbeArray"][0]["Stage_X"]
        updated_y = updated_status["ProbeArray"][0]["Stage_Y"]
        updated_z = updated_status["ProbeArray"][0]["Stage_Z"]
        print(f"Attempt {attempt + 1}: Updated X, Y, Z positions: {updated_x}, {updated_y} {updated_z}")

        # Check if the stage has reached the target positions within tolerance
        if abs(updated_z-15.0) < 0.02:
            print("Stage successfully moved.")
            break
    else:
        # If the loop completes without breaking, the movement did not occur as expected
        pytest.fail(f"Stage did not move to the target position: expected ({target_x}, {target_y}, {15.0}), "
                    f"but got ({updated_x}, {updated_y}, {updated_z}).")