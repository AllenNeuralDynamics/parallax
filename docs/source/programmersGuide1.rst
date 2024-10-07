*Programmer's Guide*

Reticle Detection
--------------------


**Overview**

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
                <img src="_static/_progGuide/_reticleDetect/_1_general/5_calib.jpg" width="180px"/>
                <div style="font-size: 10px;">Camera Calibration</div>
            </div>
        </div>
    </div>
    <br>

Reticle detection involves a computer vision pipeline. Here is the general process:

    1. **Original Image:** This is the starting point, where you can view a reticle from the camera.

    2. **Mask Generated:** A mask is created from the original image in binary form. This mask highlights or separates key areas of the image—the reticle—from the background, including the metal parts of the reticle window, making it easier for further processing.

    3. **Coordinates Detection:** Once the mask is generated, the system detects the markers from the image for further analysis.

    4. **Get Interest Points:** After detecting the coordinates, the system aligns and identifies several central points on the reticle used for calibration purposes. Additionally, the user can select which axis represents the x-axis from the camera's perspective.

    5. **Camera Calibration:** In this final step, stereo camera calibration is performed using the detected points. This calibration is essential for 3D reconstruction of the probe tip location in later process.

Please continue reading the rest of the document for detailed steps.

----

**Mask Generation**

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
        <br>


    1. **Resize:**
        The image is resized to smaller for faster processing.
        If the image has more than 2 channels (e.g., color), it is first converted to grayscale.
            
    2. **Frame Detection:**
        A homomorphic filter is applied to enhance the image by removing shadows and normalizing brightness.
        A binary thresholding technique is then applied to the image using Otsu’s method to separate the reticle from the background.
        
    3. **Thresholding:**
        The image is converted into a binary mask where the reticle and other key features are highlighted. The thresholding step converts pixel values to either 0 or 255 depending on their intensity, creating a sharp contrast between the reticle and the background.
        
    4. **Remove Blobs:**
        Small noise or irrelevant blobs, such as reflections on the reticle's metal window, are removed from the image. Contours are detected, and only the largest contour (likely the reticle) is retained, while the others are filled in or removed.

    5. **Invert Image and Remove Blobs:**
        The binary mask is inverted so that the reticle becomes the foreground, and any small noise or blobs, such as reflections on the reticle surface, are further cleaned up by detecting and removing small contours.

    6. **Resize to Original:**
        The processed image is resized back to its original size, ensuring the final mask matches the dimensions of the original input image.
        
    7. **Grey Image:**
        After processing, the image is converted back into an 8-bit single-channel grayscale format, ready for further analysis or use in later steps.
        This process results in a clean, noise-free mask that highlights the reticle, making it easier to detect and calibrate the reticle in subsequent steps.



----

**Coordinates Detection**

    The following steps outline the process used in the ReticleDetection class for identifying reticle coordinates in microscopy images.

    1. **Masked Image**:
        .. image:: _static/_progGuide/_reticleDetect/_3_coords/1.png
            :alt: Masked Image
            :width: 400px

        The image is preprocessed by converting it to grayscale and applying a Gaussian blur. The `mask` is then applied using the `MaskGenerator` class, isolating the reticle from the background.

        - **Code Reference**: `_preprocess_image()` and `_apply_mask()` methods.


    2. **Local Thresholding**:
        .. image:: _static/_progGuide/_reticleDetect/_3_coords/2.png
            :alt: Local Thresholding
            :width: 400px

        Adaptive thresholding is applied to convert the preprocessed image into a binary image. This step separates the reticle from the background based on local pixel intensity variations.

        - **Code Reference**: `cv2.adaptiveThreshold()` in `coords_detect_morph()`.


    3. **Median Filter**:
        .. image:: _static/_progGuide/_reticleDetect/_3_coords/3.png
            :alt: Median Filter
            :width: 400px

        A median filter is applied to remove small noise by smoothing the binary image. This step helps clean up small artifacts that may have resulted from thresholding.

        - **Code Reference**: `cv2.medianBlur()` in `coords_detect_morph()`.


    4. **Invert Image**:
        .. image:: _static/_progGuide/_reticleDetect/_3_coords/5.png
            :alt: Invert Image
            :width: 400px

        The binary image is inverted so that the reticle becomes the foreground. This ensures that subsequent operations focus on the reticle itself.

        - **Code Reference**: `cv2.bitwise_not()` in `coords_detect_morph()`.


    5. **Remove Noise (Morphological Operations)**:
        .. image:: _static/_progGuide/_reticleDetect/_3_coords/6.png
            :alt: Remove Noise
            :width: 400px
        
        Morphological operations, such as closing and opening, are applied to remove small noise and refine the mask structure by eliminating small blobs.

        - **Code Reference**: `cv2.morphologyEx()` in `coords_detect_morph()`.


    6. **Eroding**:
        .. image:: _static/_progGuide/_reticleDetect/_3_coords/7.png
            :alt: Eroding
            :width: 400px
        
        Eroding continues until the system finds a sufficient number of blobs (50 < x < 300), which correspond to the reticle’s marks. It also shrinks objects in the image, removing unnecessary small contours and refining the reticle structure.

        - **Code Reference**: `_eroding()` method.


    7. **RANSAC to Detect Lines**:
        .. image:: _static/_progGuide/_reticleDetect/_3_coords/8.png
            :alt: RANSAC to Detect Lines
            :width: 400px
        
        The RANSAC algorithm is used to detect the reticle lines by fitting line models to the inlier points. This method helps handle noisy data.

        - **Code Reference**: `_ransac_detect_lines()` method.


    8. **Detect 2nd Line**:
        .. image:: _static/_progGuide/_reticleDetect/_3_coords/9.png
            :alt: Detect 2nd Line
            :width: 400px
        
        After detecting the first line using RANSAC, the inliers (first line) are removed, and then the second line is detected using RANSAC again. This step ensures that both the x-axis and y-axis lines are detected.

        - **Code Reference**: The second line is detected in `_ransac_detect_lines()`.


    9. **Interpolate Missing Points**:
        .. image:: _static/_progGuide/_reticleDetect/_3_coords/10.png
            :alt: Interpolate Missing Points
            :width: 400px

        Missing points in the detected lines are interpolated to fill gaps between the detected points, ensuring the lines are continuous.

        - **Code Reference**: `_estimate_missing_points()` and `_add_missing_pixels()` methods.


    9. **Get Interest Points**:
        .. image:: _static/_progGuide/_reticleDetect/_3_coords/11.png
            :alt: Get Interest Points
            :width: 400px

        Pixels of interest are extracted around the reticle.
        
        - **Code Reference**: `_get_pixels_interest()` method.