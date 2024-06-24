Welcome to Parallax
====================

.. image:: ../../ui/ParallaxReadME.jpg
   :alt: Parallax

Parallax is a graphical user interface designed to streamline the process of setting up and performing acute in vivo electrophysiology experiments.

Prerequisites
--------------
   - **Python~=3.8** (Recommended to install via `Anaconda`_ or `Miniconda`_)
      - Python 3.8 is required for the Spinnaker library.
   - PySpin (for Linux or Mac OS users)

   .. _Anaconda: https://www.anaconda.com/products/individual
   .. _Miniconda: https://docs.conda.io/en/latest/miniconda.html

Installing and Upgrading
-------------------------
   1. Create a virtual environment using **Python 3.8** and activate it:

      - On Windows:

      .. code-block:: bash

         python -m venv venv
         .\venv\Scripts\activate

      - On Linux/Mac:

      .. code-block:: bash

         python -m venv venv
         source venv/bin/activate

   2. Install the latest version:

      .. code-block:: bash

         pip install parallax-app

      To upgrade to the latest version:

      .. code-block:: bash

         pip install parallax-app --upgrade

   3. To install the camera interface:

      .. code-block:: bash

         pip install parallax-app[camera]

Running Parallax
----------------
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