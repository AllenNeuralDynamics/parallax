Welcome to Parallax
=========================

.. image:: ../ui/ParallaxReadME.jpg
   :alt: Parallax

Parallax is a graphical user interface designed to streamline the process of setting up and performing acute in vivo electrophysiology experiments.


Prerequisites
=========================
- **Python~=3.8** (Recommended to install via [Anaconda](https://www.anaconda.com/products/individual) or [Miniconda](https://docs.conda.io/en/latest/miniconda.html))
- PySpin (for Linux or Mac OS users)


Installing and Upgrading
=========================

1. Create virtual environment using **Python version 3.8** and activate it:
- On Windows:

.. code-block:: bash

   python -m venv venv
   ./venv/Scripts/activate

- On Linux/Mac:

.. code-block:: bash

   python -m venv venv
   source venv/bin/activate

2. To install the latest version:

.. code-block:: bash

   pip install parallax-app

To upgrate to the latest version:

.. code-block:: bash

   pip install parallax-app --upgrade


3. To install camera interface:

.. code-block:: bash
   
   pip install parallax-app[camera]


Running Parallax
=========================

.. code-block:: bash

   python -m parallax

   
Development mode
=========================

1. Clone the repository:

.. code-block:: bash

   git clone https://github.com/AllenNeuralDynamics/parallax.git

2. Install Dependencies:

.. code-block:: bash

   pip install -e .[dev]


Documentation
=========================

1. To install the dependencies:

.. code-block:: bash

   pip install -e .[docs]

2. Then to create the documentation html files, run:

.. code-block:: bash

   sphinx-build -b html docs/ docs/_build

