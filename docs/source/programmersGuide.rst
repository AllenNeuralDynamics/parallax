Programmer's Guide
====================

The Programmer's Guide provides detailed technical information on the internal workings of Parallax, from reticle detection and probe calibration to understanding the computer vision algorithms used for processing images and detecting points. This guide is designed for developers who need to extend or modify the Parallax system for custom experiments.

Key areas covered:

1. **Reticle Detection**:
   
    - The detection process involves several steps: from image preprocessing to mask generation and identifying key coordinates on the reticle.
    - Algorithms used include thresholding, morphological operations, and RANSAC for line detection.

2. **Probe Detection**:
   
    - The probe detection process uses difference imaging, Hough Line Transform, and gradient analysis to detect the tip and base of a probe.
    - Once detected, the precise tip location is determined using more refined image processing techniques, and the tracking boundary is updated accordingly.

----

.. toctree::
    :maxdepth: 1

    programmersGuide1
    programmersGuide2