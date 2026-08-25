.. Parallax documentation master file, created by
   sphinx-quickstart on Thu Mar 28 08:46:52 2024.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Parallax
====================

.. image:: _static/_front/parallax_overview.png
   :alt: Parallax

**Parallax** is a graphical user interface designed to streamline the process of setting up and performing acute *in vivo* electrophysiology experiments.
By combining multi-camera views with computer vision, Parallax reduces the complexity of experimental setup and minimizes human error during in vivo hardware insertion.

Key Features
------------

* **Photogrammetry-Assisted Targeting:** Utilizes multiple camera views to automatically detect probe positions and assist with spatial navigation.
* **Automated Reticle Detection:** Features built-in support for neural network models (such as SuperPoint and SuperGlue/LightGlue) to automatically detect and align reticles to determine the camera pose.
* **Hardware Integration:** Seamlessly interfaces with camera hardware (via the Spinnaker SDK) to provide high-speed, real-time visual feedback during setup.
Whether you are coordinating compl

Contents
==================

.. toctree::
   :maxdepth: 2

   ReadMe
   userGuide
   FAQ
   programmersGuide
   parallaxModules
   