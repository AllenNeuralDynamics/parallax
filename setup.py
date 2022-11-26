from setuptools import setup, find_packages
import os, sys

# import parallax from local path to look up current version 
sys.path.insert(0, os.path.dirname(__file__))
import parallax

packages = [x for x in find_packages('.') if x.startswith('parallax')]

setup(
    name = "parallax",
    version = parallax.__version__,
    description = "GUI software for photogrammetry-assisted probe targeting in electrophysiology",
    license = "Allen Institute Software License",
    url = "http://github.com/AllenNeuralDynamics/parallax",
    packages=packages,
)


