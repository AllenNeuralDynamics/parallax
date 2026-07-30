Getting Started
====================

Prerequisites
--------------
   - **Python 3.10**: Strictly required for compatibility with the Spinnaker library.
   - `Pathfinder MPM Control Panel`_ (v.2.8 or later)
   - `Spinnaker SDK 4.3 and PySpin`_ (Teledyne FLIR's `installation guide`_)

   .. _Pathfinder MPM Control Panel: https://newscaletech.com/multi-probe-micromanipulator/mpm-system-pathfinder-software/
   .. _Spinnaker SDK 4.3 and PySpin: https://www.teledynevisionsolutions.com/support/support-center/software-firmware-downloads/iis/spinnaker-sdk-download/spinnaker-sdk--download-files/
   .. _installation guide: https://www.teledynevisionsolutions.com/support/support-center/technical-guidance/iis/installing-pyspin-for-the-spinnaker-sdk/


Installing Parallax
-------------------
   **1. Create a virtual environment using Python 3.10 and activate it:**

      .. code-block:: bash

         uv venv --python 3.10
         # On macOS/Linux: 
         source .venv/bin/activate
         # On Windows: 
         .venv\Scripts\activate

   **2. Install Parallax:**

      *Option A: Install from PyPI*

      .. code-block:: bash

         uv pip install parallax-app

      *Option B: Install from Source (Recommended)*

      .. code-block:: bash

         git clone https://github.com/AllenNeuralDynamics/parallax.git
         cd parallax
         uv sync

   **3. Install Spinnaker (Camera Interface):**
      
      Install the full Spinnaker SDK, then install PySpin using the wheel file included with the SDK.

      .. code-block:: bash

         # Replace <WHEEL_PATH> with the full path to your .whl file:
         uv pip install "<WHEEL_PATH>"
         # Example: uv pip install spinnaker_python-4.3.0.190-cp310-cp310-win_amd64.whl


**Optional: Enable SuperPoint + LightGlue**

Parallax supports advanced reticle detection using SuperPoint and LightGlue. To enable this feature, you must manually download the required pretrained models. 

*Note: The SuperGluePretrainedNetwork is not included in this repository and is distributed under its own licensing terms. Please review their* `license <https://github.com/magicleap/SuperGluePretrainedNetwork>`_ *before use.*

**1. Install the sfm dependency:**

   .. code-block:: bash

      uv pip install git+https://github.com/AllenNeuralDynamics/sfm.git@main

**2. Clone the SuperGlue repository** into the ``external/`` folder of your Parallax project root:

   .. code-block:: bash

      git clone https://github.com/magicleap/SuperGluePretrainedNetwork.git external/SuperGluePretrainedNetwork

**3. Verify your folder structure:** Ensure it matches the following layout:

   .. code-block:: text

      parallax/
      ├── external/
      │   └── SuperGluePretrainedNetwork/
      │       └── models/
      │           ├── superpoint.py
      │           └── weights/
      │               ├── superpoint_v1.pth
      │               └── superglue_indoor.pth


Running Parallax
----------------
**1. Stage Connection Setup**

   - Run Pathfinder MPM Software (v2.8 or later) in administrator mode.
   - Navigate to **MPM System Setup**.
   - Go to the **LogFile/Http Server** tab and enable the HTTP server.
   
      .. image:: _static/_userGuide/_readMe/PathfinderHTTPServer.JPG
         :alt: Enable HTTP server
         :scale: 30%

**2. Launch Parallax:**

   .. code-block:: bash

      uv run parallax


For Developers
--------------
Ensure code quality before submitting changes by using the following commands.

**1. Install all dependencies:**

   .. code-block:: bash

      uv sync --all-extras

**2. Code Quality & Testing Tools:**

   .. code-block:: bash

      uv run pytest tests
      uv run ruff check
      uv run ruff format --check parallax
      uv run mypy parallax

**3. Build Documentation:**

To build the HTML documentation locally, run:

   .. code-block:: bash

      uv run sphinx-build -b html docs/source docs/_build