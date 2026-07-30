

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