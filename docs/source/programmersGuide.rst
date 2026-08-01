Programmer's Guide
====================

The Programmer's Guide provides detailed technical information on the internal workings of Parallax, from reticle detection and probe calibration to understanding the computer vision algorithms used for processing images and detecting points. This guide is designed for developers who need to extend or modify the Parallax system for custom experiments.

Key areas covered:

1. **Reticle Detection**:
   
    - The reticle detection pipeline provides both traditional OpenCV and modern CNN-based methodologies to identify key coordinates on the reticle grid.
    - **OpenCV Option**: Relies on classical image processing steps, including thresholding, morphological operations, mask generation, and RANSAC for line detection.
    - **CNN Option**: Utilizes Convolutional Neural Networks for reticle segmentation and feature extraction, offering improved accuracy and adaptability across varied lighting conditions and backgrounds.

2. **Probe Detection**:
   
    - Offers multiple algorithmic pathways for detecting the tip and base of a neural probe, including OpenCV, general CNN models, and a specialized YOLO pipeline.
    - **OpenCV Option**: Uses traditional computer vision methods such as difference imaging, Hough Line Transform, and gradient analysis.
    - **CNN & YOLO Options**: Employs deep learning models, including a two-stage YOLO pipeline (global segmentation and local keypoint detection).
    - Across all methods, once the general probe area is detected, the precise tip location is determined using refined image processing techniques, and the tracking boundary is updated accordingly.

----

.. toctree::
    :maxdepth: 1

    programmersGuideReticleCV
    programmersGuideReticleCNN
    programmersGuideProbeCV
    programmersGuideProbeCNN