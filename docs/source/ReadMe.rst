Getting Started
====================

Prerequisites
--------------
   - **Python~=3.8** 
      - Recommended to install via `Anaconda`_ or `Miniconda`_
      - Python 3.8 is required for the Spinnaker library.
   - `Pathfinder MPM Software`_ version 2.8.0 or later
   - `Spinnaker SDK`_ 
   - PySpin (for Linux or Mac OS users)

   .. _Anaconda: https://www.anaconda.com/products/individual
   .. _Miniconda: https://docs.conda.io/en/latest/miniconda.html
   .. _Pathfinder MPM Software: https://www.newscaletech.com/multi-probe-micromanipulator/mpm-system-pathfinder-software/
   .. _Spinnaker SDK: https://www.teledynevisionsolutions.com/products/spinnaker-sdk

Installing and Upgrading
-------------------------
   **1. Create a virtual environment using Python 3.8 and activate it:**
      - On Windows:

      .. code-block:: bash

         python -m venv venv
         ./venv/Scripts/activate

      - On Linux/Mac:

      .. code-block:: bash

         python -m venv venv
         source venv/bin/activate

   **2. Install the latest version:**
      .. code-block:: bash

         pip install parallax-app

      To upgrade to the latest version:

      .. code-block:: bash

         pip install parallax-app --upgrade

   **3. To install the camera interface:**
      .. code-block:: bash

         pip install parallax-app[camera]

Running Parallax
----------------
1. **Run the Pathfinder MPM Software application** to connect to the manipulator:

   - Run Pathfinder MPM Software (v2.8.0 or later) in administrator mode.
   - Enable the HTTP server.
      - Version 2.8.0 of the Pathfinder MPM software includes an HTTP listener that can send probe information to a client program.
      - Enable the HTTP server in the "MPM System Setup" dialog.
      - Click the "Enable HTTP Server" checkbox to turn on the service.
   
      .. image:: _static/_userGuide/_readMe/PathfinderHTTPServer.JPG
         :alt: Enable HTTP server
         :scale: 30%

2. **Run the Parallax application:**

   .. code-block:: bash

      python -m parallax


Other Things to Note
---------------------
**Development Mode**

   1. Clone the repository:

      .. code-block:: bash

         git clone https://github.com/AllenNeuralDynamics/parallax.git

   2. Install dependencies:

      .. code-block:: bash

         pip install -e .[dev]

**Documentation**

   1. Install dependencies:

      .. code-block:: bash

         pip install -e .[docs]

   2. Create the documentation HTML files:

      .. code-block:: bash

         sphinx-build -b html docs/source docs/_build