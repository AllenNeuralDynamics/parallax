import pytest

from parallax.probe_detection.yolo.detection import Detection


def test_defaults_describe_a_detection_with_nothing_found():
    det = Detection()

    assert det.class_id == -1
    assert det.confidence == 0.0
    assert det.bbox == []
    assert det.keypoints == []
    assert det.id is None
    assert det.mask is None


def test_lists_are_not_shared_between_instances():
    a, b = Detection(), Detection()

    a.bbox.append(1.0)

    assert b.bbox == []


def test_to_dict_uses_the_pipeline_keys():
    det = Detection(
        model="yolo_local",
        timestamp=5.0,
        bbox=[1, 2, 3, 4],
        class_id=2,
        class_name="probe",
        confidence=0.9,
        id=7,
        mask=[[1, 1]],
        keypoints=[10.0, 20.0, 0.9],
        stage_ts=1.5,
        bbox_seg=[5, 6, 7, 8],
    )

    assert det.to_dict() == {
        "model": "yolo_local",
        "timestamp": 5.0,
        "bbox": [1, 2, 3, 4],
        "class": 2,  # class_id is called "class" in the pipeline dicts
        "class_name": "probe",
        "confidence": 0.9,
        "id": 7,
        "mask": [[1, 1]],
        "keypoints": [10.0, 20.0, 0.9],
        "stage_ts": 1.5,
        "bbox_seg": [5, 6, 7, 8],
    }


def test_unknown_attribute_raises_instead_of_creating_a_field():
    det = Detection()

    with pytest.raises(AttributeError):
        det.mask_orig = [[1, 1]]
