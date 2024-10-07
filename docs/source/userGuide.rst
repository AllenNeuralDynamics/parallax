User Guide
====================

.. raw:: html

   <iframe width="640" height="360" src="https://www.youtube.com/embed/iLtgGqeCe1g" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>


Parallax features a :blue:`camera view system` with controls for camera parameters such as brightness, as well as snapshot and recording functions. It also connects to a stage controller to read stage coordinates.

Using the :blue:`Reticle Detection` function, it captures reticle coordinates. To obtain the 3D position of the reticle, the reticle coordinates must be detected by at least two cameras.

During :blue:`Probe Calibration`, the tip of a probe is tracked across multiple camera views. Using triangulation, it determines the 3D position. At the end of probe calibration, it displays global coordinates, showing the tip location relative to the reticle coordinates.

This page explains how to use the Parallax for basic functions, reticle calibration, and probe calibration.

----

.. toctree::
    :maxdepth: 1

    userGuideCalibration
    userGuideTrajectory
    userGuideReticleMetadata
    userGuideCalc
    userGuidePtProject