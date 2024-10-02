*Programmer's Guide*

Probe Detection
==================

Overview
--------------------

.. raw:: html

    <div class="inline-images" style="text-align: center;">
        <div style="display: inline-flex; align-items: center; justify-content: center;">
            <div style="text-align: center;">
                <img src="_static/_progGuide/_probeDetect/0_pipeline/1.png" width="180px"/>
                <div style="font-size: 10px;">Preprocessing (Diff)</div>
            </div>
            <div style="margin: 0 10px; font-size: 18px;">→</div>
            <div style="text-align: center;">
                <img src="_static/_progGuide/_probeDetect/0_pipeline/2.png" width="180px"/>
                <div style="font-size: 10px;">Line Detection</div>
            </div>
            <div style="margin: 0 10px; font-size: 18px;">→</div>
            <div style="text-align: center;">
                <img src="_static/_progGuide/_probeDetect/0_pipeline/3.png" width="180px"/>
                <div style="font-size: 10px;">Tip and Base Detection</div>
            </div>
            <div style="margin: 0 10px; font-size: 18px;">→</div>
            <div style="text-align: center;">
                <img src="_static/_progGuide/_probeDetect/0_pipeline/4.png" width="180px"/>
                <div style="font-size: 10px;">Precise tip point</div>
            </div>
            <div style="margin: 0 10px; font-size: 18px;">→</div>
            <div style="text-align: center;">
                <img src="_static/_progGuide/_probeDetect/0_pipeline/5.png" width="180px"/>
                <div style="font-size: 10px;">Update Tracking Boundary</div>
            </div>
        </div>
    </div>
    <br>

Probe detection involves a computer vision pipeline. Here is the general process:

    1. **Preprocessing:**  
    In this step, a difference image is created by comparing the current frame with the previous or background frame. This highlights the areas where motion is occurring.

    2. **Line Detection:**  
    Hough line detection is used to detect straight lines in the difference image. This helps in identifying the angle and edges of the probe within the frame.

    3. **Tip and Base Detection:**  
    The algorithm then detects the pixel coordinates of the probe's tip and base. This is for determining the probe's orientation, position, and bounding box in the frame.

    4. **Precise Tip Point:**  
    The precise tip point of the probe is calculated within the tracking boundary, improving accuracy. This ensures that the detected tip is as accurate as possible using the original image data.

    5. **Update Tracking Boundary:**  
    After detecting the probe tip, the tracking boundary is updated for the next frame. This allows the system to keep following the probe's motion accurately in subsequent frames.


Please continue reading the rest of the document for detailed steps.


----

Preprocessing
--------------------

1. **Preprocess:**

During preprocessing, the system prepares the current frame for probe detection by converting it to grayscale (if it's a color image) and resizing it for faster processing. A Gaussian blur is then applied to reduce noise in the frame, which helps in smoothing out irrelevant details before comparison. The **mask detection** step follows, where the mask generator is used to isolate the reticle from the background, ensuring that the reticle region can be processed separately.

2. Create **'Reticle zone'**

If the reticle is detected for the first time and no reticle zone is set, a `ReticleDetection` object is created to get the reticle zone, which helps in localizing the X and Y coordinates of the reticle. This reticle zone is later used to enhance probe detection by focusing only on the area of interest.

3. Create **Mask**

The mask is generated using `self.mask_detect.process()`, which prepares the frame for the subsequent stages of probe detection.

4. **Diff Image** Generation

The probe detection process comprises two main algorithms, with fallback logic that first tries the initial algorithm, which **compares the ‘Curr’ vs ‘Prev’ frame**, and if it fails, switches to the next algorithm, which **compares the ‘Curr’ vs ‘BG’ frame**. These algorithms compare different frames to detect the moving probe.

- **Comparing ‘Curr’ vs ‘Prev’ Frame**

   .. raw:: html

      <div class="inline-images" style="text-align: center;">
          <div style="display: inline-flex; align-items: center; justify-content: center;">
              <div style="text-align: center;">
                  <img src="_static/_progGuide/_probeDetect/1_fallback/1_1.png" width="150px"/>
                  <div style="font-size: 10px;">Current Frame</div>
              </div>
              <div style="margin: 0 10px; font-size: 18px;">-</div>
              <div style="text-align: center;">
                  <img src="_static/_progGuide/_probeDetect/1_fallback/1_1.png" width="150px"/>
                  <div style="font-size: 10px;">Previous Frame</div>
              </div>
              <div style="margin: 0 10px; font-size: 18px;">=</div>
              <div style="text-align: center;">
                  <img src="_static/_progGuide/_probeDetect/1_fallback/1_3.png" width="150px"/>
                  <div style="font-size: 10px;">Diff</div>
              </div>
              <div style="margin: 0 10px; font-size: 18px;">→</div>
              <div style="text-align: center;">
                  <img src="_static/_progGuide/_probeDetect/1_fallback/1_4.png" width="150px"/>
                  <div style="font-size: 10px;">Processed</div>
              </div>
          </div>
      </div>
      <br>

This algorithm compares the current frame (`Curr`) with the previous frame (`Prev`) to detect changes and thus identify the probe's movement. The difference between the two frames is processed to highlight areas where motion is occurring, enabling the system to track the probe’s movement.
    
    **Pros**:
    
    - Stronger in handling noise, as differences are calculated between consecutive frames.
    
    - Can work well when the probe moves relatively quickly.
    
    **Cons**:

    - Not effective when the probe moves slowly, as the changes between consecutive frames may be minimal and hard to detect.

    
- **Comparing ‘Curr’ vs ‘BG’ Frame**

   .. raw:: html

      <div class="inline-images" style="text-align: center;">
          <div style="display: inline-flex; align-items: center; justify-content: center;">
              <div style="text-align: center;">
                  <img src="_static/_progGuide/_probeDetect/1_fallback/2_1.png" width="150px"/>
                  <div style="font-size: 10px;">Current Frame</div>
              </div>
              <div style="margin: 0 10px; font-size: 18px;">-</div>
              <div style="text-align: center;">
                  <img src="_static/_progGuide/_probeDetect/1_fallback/2_2.png" width="150px"/>
                  <div style="font-size: 10px;">Background</div>
              </div>
              <div style="margin: 0 10px; font-size: 18px;">=</div>
              <div style="text-align: center;">
                  <img src="_static/_progGuide/_probeDetect/1_fallback/2_3.png" width="150px"/>
                  <div style="font-size: 10px;">Diff</div>
              </div>
              <div style="margin: 0 10px; font-size: 18px;">→</div>
              <div style="text-align: center;">
                  <img src="_static/_progGuide/_probeDetect/1_fallback/2_4.png" width="150px"/>
                  <div style="font-size: 10px;">Processed</div>
              </div>
          </div>
      </div>
      <br>

This algorithm compares the current frame (`Curr`) with a background frame (`BG`) that is captured when the probe is stationary or slow-moving. It detects the probe by highlighting the difference between the static background and the current frame, where the probe is in motion.
    
    **Pros**:
    
    - More effective for detecting slow-moving probes, as it compares the current frame with a static background, making even slight motion detectable.
    
    **Cons**:

    - More sensitive to noise, as changes in the environment or camera vibrations may be detected as motion.
    
    - Requires a reliable background frame, which may be challenging if there are frequent changes in the scene.
        




----

Line Detection
--------------------

TBD

----

Tip and Base Detection
-----------------------------

TBD

----



Precise Tip Point
----------------------

TBD

----

Update Tracking Boundary
----------------------------

TBD