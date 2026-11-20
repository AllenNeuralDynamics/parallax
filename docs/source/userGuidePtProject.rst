Global Coordinates Mapper from Screens
--------------------------------------------

The ``ScreenCoordsMapper`` tool allows users to calculate **global coordinates** from points clicked on camera screens.
It is useful for determining the corresponding global positions from visual data.
This guide explains how to use this feature.

----

1. **Mapping Clicked Screen Points to Global Coordinates**
   
    When you click on camera screens used for probe calibration, the system converts the clicked position into global coordinates.

2. **Steps for Screen Coordinates Mapping**:
   
    - Select the item that starts with 'Proj Global Coords' from the global coordinates dropdown menu in the UI.
    
    .. image:: _static/_userGuide/_getPts/1.jpg
        :alt: Select 'Proj Global Coords...'
        :width: 150px
        :align: center
    
    - Click on the camera screens that were used for probe calibration. The tool automatically calculates the corresponding global coordinates based on the clicked position.
    
    .. figure:: _static/_userGuide/_getPts/2.jpg
        :alt: Click on camera screens
        :width: 700px
        :align: center

        Global Point Projection

    .. figure:: _static/_userGuide/_getPts/3.jpg
        :alt: Click on Camera Screens
        :width: 700px
        :align: center

        Bregma Point Coordinates

    - If a reticle is selected, its metadata (such as offsets and rotation) will be applied to the calculated global coordinates.
