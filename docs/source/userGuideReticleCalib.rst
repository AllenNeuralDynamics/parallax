Reticle Calibration
--------------------

1. **Initiate Detection**

   Click the :blue:`Reticle Detection` button. You will be presented with two algorithm options:

   * **OpenCV**: Uses traditional computer vision methods (Hough line detection and morphology). It is fast but can be sensitive to glare on the reticle or metal reflections.
   * **SuperPoint**: Uses a deep learning model (CNN) that is more robust to varying light conditions and occlusions, but may be slower without a GPU.

   Select the algorithm that best suits your setup. You can re-run detection if the initial attempt fails.

    .. image:: _static/_userGuide/_calib/reticle_detection.jpg
        :alt: Reticle detection options

2. **Verify Detection and Accept**

   After detection, the reticle's detected axes and tick marks will be overlaid on the camera views. Zoom in on each view to verify that:

   * The detected lines align precisely with the physical reticle lines.
   * The detected x and y axes match the orientation of your physical reticle.

    .. image:: _static/_userGuide/_calib/reticle_detection_zoom.jpg
        :alt: Verify reticle alignment

   If the detection is accurate, click **Accept**. If not, click **Reject** to reset and try again.

3. **Define the Positive X-Axis**

   After accepting, you will be prompted to identify the orientation of your coordinate system. Click on the **positive x-axis** of the reticle in each camera view.

    .. image:: _static/_userGuide/_calib/reticle_detection_pos_x.jpg
        :alt: Click the positive-x coordinate

4. **Review Triangulation Results**

   Parallax will perform stereo triangulation and display the reprojection error.
    
    .. image:: _static/_userGuide/_calib/reticle_detection_result.jpg
        :alt: Reticle detection result with reprojection error

    .. tip::
        A reprojection error under **3.0 µm³** is good. An error under **5.0 µm³** is acceptable. If the error is too high, you may need to restart the calibration.

5. **Further Reading (FAQs)**

    For more details and troubleshooting, see the :ref:`FAQs <reticle_detection_faqs>`:

    - :ref:`Q. How should the reticle look in the view? <faq_r_0>`
    - :ref:`Q. Reticle is not detected. What should I do? <faq_r_1>`
    - :ref:`Q. Reprojection error is too high. How to fix it? <faq_r_2>`

