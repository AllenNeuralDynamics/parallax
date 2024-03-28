Welcome to Parallax
=========================

.. image:: ../ui/ParallaxReadME.jpg
   :alt: Parallax

Parallax is a graphical user interface designed to streamline the process of setting up and performing acute in vivo electrophysiology experiments.


Prerequisites
=========================
- Python==3.8 (Recommended to install via [Anaconda](https://www.anaconda.com/products/individual) or [Miniconda](https://docs.conda.io/en/latest/miniconda.html))
- PySpin (for Linux or Mac OS users)


Installing and Upgrading
=========================

1. To install the latest version:

.. code-block:: bash

   pip install parallax

To upgrade to the latest version:

.. code-block:: bash

   pip install parallax -upgrade


2. Create virtual environment(Python==3.8) and activate it:

- On Windows:

.. code-block:: bash

   python -m venv venv
   ./venv/Scripts/activate

- On Linux/Mac:

.. code-block:: bash

   python -m venv venv
   source venv/bin/activate

3. Install Dependencies:

.. code-block:: bash

   pip install .


Running Parallax
=========================

.. code-block:: bash

   python run-parallax.py -v2