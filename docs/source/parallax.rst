Parallax Package
================

Axis Filter Module
------------------

This module handles the filtering of axis data.

.. automodule:: parallax.axis_filter
   :members:
   :undoc-members:
   :special-members: __init__, filter_data


Bundle Adjustment Module
------------------------

This module performs bundle adjustment to refine the 3D structure.

.. automodule:: parallax.bundle_adjustment
   :members:
   :undoc-members:
   :special-members: __init__, adjust


Calculator Module
-----------------

This module contains a calculator for various mathematical functions needed in the system.

.. automodule:: parallax.calculator
   :members:
   :undoc-members:
   :special-members: __init__, calculate


Calibration Camera Module
-------------------------

This module provides camera calibration functionality.

.. automodule:: parallax.calibration_camera
   :members:
   :undoc-members:
   :special-members: __init__, calibrate


Camera Module
-------------

This module manages camera interactions, such as capturing frames and adjusting settings.

.. automodule:: parallax.camera
   :members:
   :undoc-members:
   :special-members: __init__, capture_frame, adjust_exposure


Coordinate Transformation Module
--------------------------------

This module handles transformations between different coordinate systems.

.. automodule:: parallax.coords_transformation
   :members:
   :undoc-members:
   :special-members: __init__, transform_to_global, transform_to_local


Current Background Comparison Processor Module
----------------------------------------------

This module compares the current background frame with previous frames to detect changes.

.. automodule:: parallax.curr_bg_cmp_processor
   :members:
   :undoc-members:
   :special-members: __init__, compare_frames


Current Previous Comparison Processor Module
--------------------------------------------

This module compares current frames with previous ones to track changes over time.

.. automodule:: parallax.curr_prev_cmp_processor
   :members:
   :undoc-members:
   :special-members: __init__, process_comparison


Main Window WIP Module
----------------------

This module manages the main window user interface components.

.. automodule:: parallax.main_window_wip
   :members:
   :undoc-members:
   :special-members: __init__, show_window


Mask Generator Module
---------------------

This module generates masks for image processing tasks.

.. automodule:: parallax.mask_generator
   :members:
   :undoc-members:
   :special-members: __init__, generate_mask


Model Module
------------

This module defines the core model for the application.

.. automodule:: parallax.model
   :members:
   :undoc-members:
   :special-members: __init__, update_state


No Filter Module
----------------

This module defines a pass-through filter with no changes.

.. automodule:: parallax.no_filter
   :members:
   :undoc-members:
   :special-members: __init__, apply_filter


Probe Calibration Module
------------------------

This module manages the calibration of the probe.

.. automodule:: parallax.probe_calibration
   :members:
   :undoc-members:
   :special-members: __init__, calibrate_probe


Probe Detect Manager Module
---------------------------

This module manages the detection of probes in images.

.. automodule:: parallax.probe_detect_manager
   :members:
   :undoc-members:
   :special-members: __init__, detect_probe


Probe Detector Module
---------------------

This module contains methods for detecting probes in the environment.

.. automodule:: parallax.probe_detector
   :members:
   :undoc-members:
   :special-members: __init__, detect_tip


Probe Fine Tip Detector Module
------------------------------

This module detects fine tips of probes.

.. automodule:: parallax.probe_fine_tip_detector
   :members:
   :undoc-members:
   :special-members: __init__, detect_fine_tip


Recording Manager Module
------------------------

This module manages the recording of data during the session.

.. automodule:: parallax.recording_manager
   :members:
   :undoc-members:
   :special-members: __init__, record_data


Reticle Detect Manager Module
-----------------------------

This module handles the detection and tracking of reticles.

.. automodule:: parallax.reticle_detect_manager
   :members:
   :undoc-members:
   :special-members: __init__, detect_reticle


Reticle Detection Module
------------------------

This module provides the core methods for detecting reticles.

.. automodule:: parallax.reticle_detection
   :members:
   :undoc-members:
   :special-members: __init__, detect_shape


Reticle Detection Coordinates Interests Module
----------------------------------------------

This module deals with detecting specific points of interest in reticle coordinates.

.. automodule:: parallax.reticle_detection_coords_interests
   :members:
   :undoc-members:
   :special-members: __init__, find_interests


Screen Widget Module
--------------------

This module provides screen interaction components.

.. automodule:: parallax.screen_widget
   :members:
   :undoc-members:
   :special-members: __init__, update_screen


Stage Listener Module
---------------------

This module listens for changes in the stage and processes events.

.. automodule:: parallax.stage_listener
   :members:
   :undoc-members:
   :special-members: __init__, listen


Stage UI Module
---------------

This module provides UI components for controlling the stage.

.. automodule:: parallax.stage_ui
   :members:
   :undoc-members:
   :special-members: __init__, update_ui


Stage Widget Module
-------------------

This module contains the UI components for the stage.

.. automodule:: parallax.stage_widget
   :members:
   :undoc-members:
   :special-members: __init__, update_widget


Utils Module
------------

This module contains utility functions used across the project.

.. automodule:: parallax.utils
   :members:
   :undoc-members:
   :special-members: __init__, helper_method
