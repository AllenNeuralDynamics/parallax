FAQs
================

.. _reticle_detection_faqs:

Reticle Detection
------------------------

.. _faq_r_0:

- **How can I optimize my reticle for automated detection?**
    
    Make sure your reticle appears similar to these examples:

    .. image:: _static/reticleDetection.jpg
        :scale: 20%

    - **Centered and in focus:** The reticle should be well-centered in the view, with its center in clear focus.

    - **Properly illuminated:** The reticle should be evenly lit without any harsh reflections or shadow regions.

    - **Appropriate size:** The reticle should occupy a significant portion of the view, without being too small or too large.

    - **Clear and unobstructed:** The reticle surface should be clean, free of debris, dirt, or any obstructions, including probes, that could interfere with detection. 

    - **Consistent background:** The reticle background should be plain and consistent, without any patterns or irregularities that might affect detection. We recommending sticking some white paper to the back of the reticle to provide a consistent background.

.. _faq_r_1:

- **What can I do if automated reticle detection is not working?**
    
    Possible reasons and solutions:
    
    1. Brightness is too high or too low:

        .. image:: _static/r_problem1.jpg
            :scale: 20%

        - Solution: Adjust the brightness to the optimal level.

        .. image:: _static/r_problem2.jpg
            :scale: 20%
    
    2. Reticle is out of focus:

        .. image:: _static/r_problem4.jpg
            :scale: 20%    

        - Solution: Move the camera relative to the reticle so that the center of the reticle is in focus. 

    3. Reticle view is too small:

        - Solution: Zoom in the camera view so that the reticle view is larger.
    
    4. Only partial reticle is visible:

        .. image:: _static/r_problem5.jpg
            :scale: 20%   

        - Solution: Ensure the reticle is well-centered in the view.
    
    5. Inconsistent lighting such as light reflection or shadow regions:

        .. image:: _static/r_problem13.jpg
            :scale: 20%   
        
        .. image:: _static/r_problem11.jpg
            :scale: 20%   

        - Solution: Make sure the reticle background has consistent lighting.
    
    6. Occlusion of reticle due to dirt or debris:

        .. image:: _static/r_problem9.jpg
            :scale: 20%   

        - Solution: Clean the reticle surface to remove any debris or dirt.
    
    7. Inconsistent background images:
    
        - Solution: Make sure there are no non-uniformities in the reticle background. Attaching plain white paper to the back of the reticle is recommended.

    8. Reticle background is too dark:
        
        .. image:: _static/r_problem12.jpg
            :scale: 20%  
    
        - Solution: Use a white paper as a background to increase the contrast between the reticle and the background.  


.. _faq_r_2:

- **How can I fix high reprojection error?**

    Possible reasons and solutions:

    1. Debris or dirt on the reticle surface causing misalignment:

        - Solution: Clean the reticle surface to remove any debris or dirt, which the algorithm may mistakenly identify as part of the reticle.
    
    2. View is too far from the reticle, making it appear too small:

        - Solution: Move the camera closer to the reticle to ensure it occupies a larger portion of the view.

    3. Reticle view is too skewed, causing a small in-focus region:

        - Solution: Adjust the camera position so that the view is less skewed, and the face of the reticle appears as flat as possible.


.. _general_faqs:

General Interface
------------------------

.. _faq_g_1:

- **If I turn on Parallax, it shows noisy data on the view and does not display the camera view. What should I do?**

    Parallax is currently under development, and some functions are not stable. If camera resources are not cleared up in the previous session, such as when the app exits forcefully or the camera interface is unplugged, it can cause this issue.
    
        .. image:: _static/reset1.jpg
            :scale: 20%
    
    - Solution: Use Spinview to reset the camera resources. Steps to reset the camera resources:

        1. Close Parallax.
        2. Open Spinview and start and stop streaming on all cameras to reset the camera resources.
        
            .. image:: _static/reset2.jpg
                :scale: 30%
        
            .. image:: _static/reset3.jpg
                :scale: 30%

        3. Launch Parallax again.