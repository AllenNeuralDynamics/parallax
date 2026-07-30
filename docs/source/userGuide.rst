User Guide
====================
.. raw:: html

   <div style="text-align: center; margin-bottom: 20px;">
      <iframe width="560" height="315" src="https://www.youtube.com/embed/lYotKVTJtmQ" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
   </div>

Parallax provides a :blue:`camera view system` that offers controls for camera parameters like framerate, auto-adjustment, along with snapshot and recording capabilities.

The :blue:`Reticle Detection` function is used to capture the coordinates of the on-screen reticle. To calculate the reticle's 3D position through triangulation, its coordinates must be detected by at least two cameras.

During :blue:`Probe Calibration`, Parallax tracks the probe tip across multiple camera views. It then uses triangulation to determine the probe's 3D position. Once calibration is complete, the system displays the probe tip's global coordinates relative to the calibrated reticle position.


----

.. toctree::
    :maxdepth: 1

    userGuideReticleCalib
    userGuideProbeCalib
    userGuideTrajectory
    userGuideReticleMetadata
    userGuideCalc
    userGuidePtProject