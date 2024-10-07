# Parallax

![Parallax](ui/ParallaxReadMe.png)

Parallax is a graphical user interface designed to streamline the process of 
setting up and performing acute *in vivo* electrophysiology experiments.

**Documentation**: [parallax.readthedocs.io](https://parallax.readthedocs.io/en/latest/index.html).

### Prerequisites
- **Python==3.8** (Recommended to install via 
[Anaconda](https://www.anaconda.com/products/individual) or 
[Miniconda](https://docs.conda.io/en/latest/miniconda.html))
  -  Python 3.8 is required for the Spinnaker library.
- PySpin (for Linux or Mac OS users)
- [Spinnaker SDK](https://www.teledynevisionsolutions.com/products/spinnaker-sdk)


### Installation
1. Create a virtual environment with **Python 3.8** and activate it:
- On Windows:
```bash
conda create -n parallax python=3.8
conda activate parallax
```

2. To install Parallax into a fresh environment, run:
```bash
pip install parallax-app
```

To upgrade to the latest version, run:
```bash
pip install parallax-app --upgrade
```

3. To install the camera interface:
```bash
pip install parallax-app[camera]
```

#### Additional Setup for Linux and macOS
* Download the Spinnaker SDK package for your system [here](https://flir.app.boxcn.net/v/SpinnakerSDK)
* Follow the installation instructions in the README
* Install the Python bindings found alongside the SDK package

### Running Parallax
```bash
python -m parallax
```

### For developers:
1. Clone the repository:
```bash
git clone https://github.com/AllenNeuralDynamics/parallax.git
```
2. Install the package along with dev dependencies:
```bash
pip install -e .[dev]
```

### Documentation
1. To install the dependencies:
```bash
pip install -e .[docs]
```
2. Then to create the documentation html files, run:
```bash
sphinx-build -b html docs/ docs/_build
```

### Support and Contribution
If you encounter any problems or would like to contribute to the project, 
please submit an [Issue](https://github.com/AllenNeuralDynamics/parallax/issues) 
on GitHub.

### License
Parallax is licensed under the MIT License. For more details, see 
the [LICENSE](LICENSE) file.
