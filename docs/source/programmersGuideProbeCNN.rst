*Programmer's Guide*

Probe Detection (CNN)
---------------------

**Overview**

The probe detection module utilizes a two-stage YOLO-based pipeline to identify and locate neural probes and their tips. This approach is designed to detect both single-shank and multi-shank probes. To balance computational performance with pixel precision, the algorithm is divided into a **Global phase** (segmentation) and a **Local phase** (keypoint detection).

.. figure:: /_static/_progGuide/_probeDetect/5_yolo/global.jpg
   :alt: Global YOLO Detection
   :align: center
   :width: 500px

   Global YOLO Detection: The system first identifies the general region of the probe.
   
.. figure:: /_static/_progGuide/_probeDetect/5_yolo/local.jpg
   :alt: Local YOLO Detection
   :align: center
   :width: 500px

   Local YOLO Detection: Then, the system zooms in to detect the tip locations.


**Processing Pipeline**

The pipeline switches between a global detection mode and a local detection mode based on probe movement.

Global Detection (Segmentation)

The global phase is responsible for finding the generalized region of the probe within the full, uncropped camera frame. 
This is the primary detection method used when the probe is in motion and stationary.

**Preprocessing**

The input frame is standardized to a 3-channel grayscale representation and downscaled to a target dimension (default ``640x640``).

**Inference**

The global YOLO model (``global_segmentation_fast.pt``) processes the downscaled image to output a bounding box and a polygon segmentation mask.

**Postprocessing**

The bounding box and polygon coordinates are scaled back up to map accurately to the original high-resolution image dimensions.

.. note::
   If the mechanical stage is actively moving (``probe_stopped == False``), the system relies solely on this global detection for general tracking and skips the more computationally expensive local phase.

Local Detection (Keypoints)

When the stage comes to a halt (``probe_stopped == True``), the system requires higher precision to identify the exact coordinates of the probe tips. 
It triggers the local detection phase, utilizing the spatial context provided by the global model.

**Preprocessing**

1. A bounding box margin (e.g., 30 pixels) is added to the global bounding box to define a crop region on the original high-resolution frame.
2. The global segmentation mask is converted into an image stencil. A morphological dilation is applied using a configurable ``mask_margin`` to slightly enlarge the unmasked area.
3. ``cv2.bitwise_and`` is applied using this stencil to black out the background noise, isolating only the probe itself.
4. The cropped, masked image is resized to ``320x320``.

**Inference**

The local YOLO model (``tip_keypoint_detection_accurate.pt``) evaluates the masked crop to detect the keypoints representing the shanks/tips. 

**Postprocessing and Refinement**

Keypoint coordinates are first rescaled and offset based on the original crop location to map them back to the full-resolution frame space.
They then undergo a final refinement step using the :meth:`parallax.probe_fine_tip_detector.ProbeFineTipDetector.get_precise_tip` method,
which evaluates a small patch (e.g., 25x25 pixels) around the YOLO-detected tip with traditional computer vision techniques to achieve sub-pixel accuracy.

**Movement Tracking**

The ``YoloProcessWorker`` tracks micro-movements of the probe by comparing the spatial position of the first detected keypoint between consecutive frames.
The Euclidean distance is calculated; if the distance exceeds the configured ``movement_threshold`` (default: 8.0 pixels), the probe is flagged as moving (``is_moving = True``).

**Configuration**

Algorithm parameters are defined in a YAML configuration file. Key settings include:

* **Segmentation (Global)**: Uses ``global_segmentation_fast.pt`` at a ``640x640`` resolution with a confidence threshold of 0.6.
* **Keypoints (Local)**: Uses ``tip_keypoint_detection_accurate.pt`` at a ``320x320`` resolution with a confidence threshold of 0.2. This phase relies on ``apply_mask: True``, utilizing a ``bbox_margin`` of 30 and a ``mask_margin`` of 15 to ensure clean crops free of background interference.