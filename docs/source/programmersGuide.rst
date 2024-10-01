Programmer's Guide
====================

Reticle Detection
--------------------

**Process)** 

.. raw:: html

    <div class="inline-images" style="text-align: center;">
        <div style="display: inline-flex; align-items: center; justify-content: center;">
            <div style="text-align: center;">
                <img src="_static/_progGuide/_reticleDetect/_1_general/1_org.png" width="180px"/>
                <div style="font-size: 10px;">Original Image</div>
            </div>
            <div style="margin: 0 10px; font-size: 18px;">→</div>
            <div style="text-align: center;">
                <img src="_static/_progGuide/_reticleDetect/_1_general/2_mask.png" width="180px"/>
                <div style="font-size: 10px;">Mask Generated</div>
            </div>
            <div style="margin: 0 10px; font-size: 18px;">→</div>
            <div style="text-align: center;">
                <img src="_static/_progGuide/_reticleDetect/_1_general/3_coordsDetect.png" width="180px"/>
                <div style="font-size: 10px;">Coordinates Detection</div>
            </div>
            <div style="margin: 0 10px; font-size: 18px;">→</div>
            <div style="text-align: center;">
                <img src="_static/_progGuide/_reticleDetect/_1_general/4_interestPts.png" width="180px"/>
                <div style="font-size: 10px;">Get Interest Points</div>
            </div>
            <div style="margin: 0 10px; font-size: 18px;">→</div>
            <div style="text-align: center;">
                <img src="_static/_progGuide/_reticleDetect/_1_general/5_calib.JPG" width="180px"/>
                <div style="font-size: 10px;">Camera Calibration</div>
            </div>
        </div>
    </div>
    <br>

Reticle detection involves a computer vision pipeline. Here is the general process:

    **Original Image:** This is the starting point, where you can view a reticle from the camera.

    **Mask Generated:** A mask is created from the original image in binary form. This mask highlights or separates key areas of the image—the reticle—from the background, including metal parts of the reticle window, making it easier for further processing.

    **Coordinates Detection:** Once the mask is generated, the system detects the markers from the image for further analysis.

    **Get Interest Points:** After detecting the coordinates, the system aligns and identifies several central points on the reticle used for calibration purposes. Additionally, the user can select which axis represents the x-axis from the camera's perspective.

    **Camera Calibration:** In this final step, stereo camera calibration is performed using the detected points. This calibration is essential for 3D reconstruction of the probe tip location in later process.

Please continue reading the rest of the document for detailed steps.

----

**Mask Generation)** 

.. raw:: html

    <div class="inline-images" style="text-align: center;">
        <div style="display: inline-flex; align-items: center; justify-content: center;">
            <div style="text-align: center;">
                <img src="_static/_progGuide/_reticleDetect/_2_mask/1_resize.png" width="180px"/>
                <div style="font-size: 10px;">Resize</div>
            </div>
            <div style="margin: 0 10px; font-size: 18px;">→</div>
            <div style="text-align: center;">
                <img src="_static/_progGuide/_reticleDetect/_2_mask/2_frame.png" width="180px"/>
                <div style="font-size: 10px;">Frame Detection</div>
            </div>
            <div style="margin: 0 10px; font-size: 18px;">→</div>
            <div style="text-align: center;">
                <img src="_static/_progGuide/_reticleDetect/_2_mask/3_globalThreshold.png" width="180px"/>
                <div style="font-size: 10px;">Thresholding</div>
            </div>
            <div style="margin: 0 10px; font-size: 18px;">→</div>
            <div style="text-align: center;">
                <img src="_static/_progGuide/_reticleDetect/_2_mask/4_remove.png" width="180px"/>
                <div style="font-size: 10px;">Remove Blobs</div>
            </div>
            <div style="margin: 0 10px; font-size: 18px;">→</div>
            <div style="text-align: center;">
                <img src="_static/_progGuide/_reticleDetect/_2_mask/5_remove.png" width="180px"/>
                <div style="font-size: 10px;">Invert Image and Remove Blobs</div>
            </div>
            <div style="margin: 0 10px; font-size: 18px;">→</div>
            <div style="text-align: center;">
                <img src="_static/_progGuide/_reticleDetect/_2_mask/6_resize.png" width="180px"/>
                <div style="font-size: 10px;">Resize to Original</div>
            </div>
            <div style="margin: 0 10px; font-size: 18px;">→</div>
            <div style="text-align: center;">
                <img src="_static/_progGuide/_reticleDetect/_2_mask/7_grey.png" width="180px"/>
                <div style="font-size: 10px;">Grey Image</div>
            </div>
        </div>
    </div>


----

** Coordinates Detection)** 




----

** Get Interest Points)** 


----

** Camera Calibration)** 



----

Probe Detection
--------------------
