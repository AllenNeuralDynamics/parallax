*User Guide*

Reticle Calibration
--------------------

1. Click on the :blue:`Reticle Detection` button.

    .. image:: _static/_userGuide/_calib/reticleDetection.JPG
        :alt: reticle detection

    - The reticle will be detected and displayed in the camera view.
    - The camera view will display reticle coordinate ticks and the x, y, z axes.
    - Visually inspect the results, and click 'Accept' if the reticle is detected correctly. Otherwise, click 'Reject' to reset.

2. Click the positive-x coordinate of the reticle on each camera view.

    .. image:: _static/_userGuide/_calib/reticleDetection_posX.JPG
        :alt: positive-x coordinate

3. Reprojection error of reticle points will appear.
    
    .. image:: _static/_userGuide/_calib/reticleDetection_result.JPG
        :alt: positive-x coordinate

    - Tips: An error under 3.0 µm³ is good. An error under 5.0 µm³ is acceptable.

4. For more details, see the :ref:`FAQs <reticle_detection_faqs>`

    - :ref:`Q. How should the reticle look in the view? <faq_r_0>`

    - :ref:`Q. Reticle is not detected. What should I do? <faq_r_1>`

    - :ref:`Q. Reprojection error is too high. How to fix it? <faq_r_2>`


----

Probe Calibration
------------------

1. Select the stage you would like to calibrate after finishing reticle calibration.

    .. image:: _static/_userGuide/_calib/probeSelect.JPG
        :alt: probe selection


2. Move the probe tip close to the reticle surface and click on the :blue:`Probe Calibration` button.

    .. image:: _static/_userGuide/_calib/probeCalib1.JPG
        :alt: probe selection

    Tip: Bring the probe tip close to the reticle surface, as the focus in the camera view is set to the reticle. This helps detect the probe tip location more precisely.
    
3. Move the probe in the x, y, z directions at least 2 mm.

    .. image:: _static/_userGuide/_calib/probeCalib2.JPG
        :alt: probe calibration

    - When moving the probe, continue alternating between stopping and moving the stage. When the stage is stopped, the tip point color turns red, representing the points used for probe calibration. When the stage is moving, the tip turns yellow, indicating only the location of the stage. Therefore, it is necessary to stop several times for the probe calibration process.
    - Once the probe has traveled far enough along each axis, the UI for the corresponding axis will turn green.
    - Even if all axes are green, additional movement may be necessary to improve the fit between the local motor coordinates and the global 3D points.

        .. image:: _static/_userGuide/_calib/probeCalib3.JPG
            :alt: probe trajectory
            :scale: 20%

4. After calibration, the UI will turn green and the global coordinates will display the tip location relative to the reticle coordinates.

    - Global coordinates show the probe tip location in the reticle coordinate system.
    - Tip: Try to hit a known point, such as the center of the reticle, to check the accuracy of the probe calibration.
    
        .. image:: _static/_userGuide/_calib/probeCalib4.JPG
            :alt: probe calibration
            :scale: 20%

5. Repeat steps 1-4 for any other probes that need to be calibrated.