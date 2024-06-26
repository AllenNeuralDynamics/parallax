User Guide
====================

Parallax features a :blue:`camera view system` with controls for camera parameters such as brightness, as well as snapshot and recording functions. It also connects to a stage controller to read stage coordinates.

Using the :blue:`Reticle Detection` function, it captures reticle coordinates. To obtain the 3D position, at least two cameras are required, and coordinates must be detected by both.

During :blue:`Probe Calibration`, the process tracks the probe tip location in the camera views. Using triangulation, it determines the 3D position. At the end of probe calibration, it displays global coordinates, showing the tip location relative to the reticle coordinates.

This page explains how to use the Parallax for basic functions, reticle calibration, and probe calibration.


.. User Interface
------------------



Reticle Calibration
--------------------
1. Click on the :blue:`Reticle Detection` button.

    .. image:: _static/reticleDetection.jpg
        :alt: reticle detection

    - The reticle will be detected and displayed in the camera view.
    - The camera view will display reticle coordinate ticks and the x, y, z axes.
    - Visually inspect the results, and click 'Accept' if the reticle is detected correctly. Otherwise, click 'Reject' to reset.

2. Then click the positive-x coordinate of the reticle on each camera view.

    .. image:: _static/reticleDetection_posX.jpg
        :alt: positive-x coordinate


3. Reprojection error of reticle points will show up.
    
    .. image:: _static/reticleDetection_result.jpg
        :alt: positive-x coordinate

    - Tips: An error under 3.0 µm³ is good. An error under 5.0 µm³ is acceptable.

4. For more details, see the :ref:`FAQs <reticle_detection_faqs>`

    - :ref:`Reticle is not detected. What should I do? <faq_r_1>`


Probe Calibration
------------------

1. Select the stage you would like to calibrate after finishing reticle calibration.

    .. image:: _static/probeSelect.jpg
        :alt: probe selection


2. Move the probe tip close to the reticle surface and click on the :blue:Probe Calibration button.

    .. image:: _static/probeCalib1.jpg
        :alt: probe selection

    Tips: Bring the probe tip close to the reticle surface, as the focus in the camera view is set to the reticle. This helps in detecting the precise probe tip location.
    
3. Move the probe in the x, y, z directions at least 2 mm.

    .. image:: _static/probeCalib2.jpg
        :alt: probe calibration

    - If the probe travels enough length in each axis, the UIs corresponding axis will turn green.
    - If the x, y, z UIs turn green but the probe calibration is not finished, keep moving the probe.
    - Tips: Move the probe tip in the reticle background to reduce noise.

        .. image:: _static/probeCalib3.jpg
            :alt: probe trajectory
            :scale: 20%

4. After calibration, the UI will turn green and the global coordinates will display the tip location relative to the reticle coordinates.

    - Global coordinates show the probe tip location in the global coordinate system.
    - Tips: Try to hit a known point, such as the center of the reticle, to check the accuracy of the probe calibration after calibration.
    
        .. image:: _static/probeCalib4.jpg
            :alt: probe calibration
            :scale: 20%

5. Select other probes if any to preceed with the calibration.

6. For more details, see the :ref:`FAQs <probe_detection_faqs>`.

    - :ref:`What information is showing? <faq_p_1>`
