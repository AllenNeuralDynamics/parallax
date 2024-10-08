Module Description
================

Calculator
----------

This module contains a calculator for various mathematical functions needed in the system.

.. automodule:: parallax.calculator
   :members:
   :undoc-members:
   :special-members: __init__, calculate


Calibration Camera
------------------

This module provides camera calibration functionality.

.. automodule:: parallax.calibration_camera
   :members:
   :undoc-members:
   :special-members: __init__, calibrate


Camera
------

This module manages camera interactions, such as capturing frames and adjusting settings.

.. automodule:: parallax.camera
   :members:
   :undoc-members:
   :special-members: __init__, capture_frame, adjust_exposure


Coordinate Transformation
-------------------------

This module handles transformations between different coordinate systems.

.. automodule:: parallax.coords_transformation
   :members:
   :undoc-members:
   :special-members: __init__, transform_to_global, transform_to_local


Current Background Comparison Processor
---------------------------------------

This module compares the current background frame with previous frames to detect changes.

.. automodule:: parallax.curr_bg_cmp_processor
   :members:
   :undoc-members:
   :special-members: __init__, compare_frames


Current Previous Comparison Processor
-------------------------------------

This module compares current frames with previous ones to track changes over time.

.. automodule:: parallax.curr_prev_cmp_processor
   :members:
   :undoc-members:
   :special-members: __init__, process_comparison


Main Window WIP
---------------

This module manages the main window user interface components.

.. automodule:: parallax.main_window_wip
   :members:
   :undoc-members:
   :special-members: __init__, show_window


Mask Generator
--------------

This module generates masks for image processing tasks.

.. automodule:: parallax.mask_generator
   :members:
   :undoc-members:
   :special-members: __init__, generate_mask


Model
-----

This module defines the core model for the application.

.. automodule:: parallax.model
   :members:
   :undoc-members:
   :special-members: __init__, update_state


No Filter
---------

This module defines a pass-through filter with no changes.

.. automodule:: parallax.no_filter
   :members:
   :undoc-members:
   :special-members: __init__, apply_filter


Axis Filter
-----------

This module handles the filtering of axis data.

.. automodule:: parallax.axis_filter
   :members:
   :undoc-members:
   :special-members: __init__, filter_data


Bundle Adjustment
-----------------

This module performs bundle adjustment to refine the 3D structure.

.. automodule:: parallax.bundle_adjustment
   :members:
   :undoc-members:
   :special-members: __init__, adjust


Probe Calibration
-----------------

This module manages the calibration of the probe.

.. automodule:: parallax.probe_calibration
   :members:
   :undoc-members:
   :special-members: __init__, calibrate_probe


Probe Detect Manager
--------------------

This module manages the detection of probes in images.

.. automodule:: parallax.probe_detect_manager
   :members:
   :undoc-members:
   :special-members: __init__, detect_probe


Probe Detector
--------------

This module contains methods for detecting probes in the environment.

.. automodule:: parallax.probe_detector
   :members:
   :undoc-members:
   :special-members: __init__, detect_tip


Probe Fine Tip Detector
-----------------------

This module detects fine tips of probes.

.. automodule:: parallax.probe_fine_tip_detector
   :members:
   :undoc-members:
   :special-members: __init__, detect_fine_tip


Recording Manager
-----------------

This module manages the recording of data during the session.

.. automodule:: parallax.recording_manager
   :members:
   :undoc-members:
   :special-members: __init__, record_data


Reticle Detect Manager
----------------------

This module handles the detection and tracking of reticles.

.. automodule:: parallax.reticle_detect_manager
   :members:
   :undoc-members:
   :special-members: __init__, detect_reticle


Reticle Detection
-----------------

This module provides the core methods for detecting reticles.

.. automodule:: parallax.reticle_detection
   :members:
   :undoc-members:
   :special-members: __init__, detect_shape


Reticle Detection Coordinates Interests
---------------------------------------

This module deals with detecting specific points of interest in reticle coordinates.

.. automodule:: parallax.reticle_detection_coords_interests
   :members:
   :undoc-members:
   :special-members: __init__, find_interests


Screen Widget
-------------

This module provides screen interaction components.

.. automodule:: parallax.screen_widget
   :members:
   :undoc-members:
   :special-members: __init__, update_screen


Stage Listener
--------------

This module listens for changes in the stage and processes events.

.. automodule:: parallax.stage_listener
   :members:
   :undoc-members:
   :special-members: __init__, listen


Stage UI
--------

This module provides UI components for controlling the stage.

.. automodule:: parallax.stage_ui
   :members:
   :undoc-members:
   :special-members: __init__, update_ui


Stage Widget
------------

This module contains the UI components for the stage.

.. automodule:: parallax.stage_widget
   :members:
   :undoc-members:
   :special-members: __init__, update_widget


Utils
-----

This module contains utility functions used across the project.

.. automodule:: parallax.utils
   :members:
   :undoc-members:
   :special-members: __init__, helper_method
