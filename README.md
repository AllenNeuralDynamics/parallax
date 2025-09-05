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
- [Spinnaker SDK 4.2](https://www.teledynevisionsolutions.com/products/spinnaker-sdk)


### Installation
1. Create a virtual environment with **Python 3.8** and activate it:
- On Windows:
```bash
conda create -n parallax python=3.10
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

3. Install the camera interface (Spinnaker Python)
Install from the **wheel file** that comes with the Spinnaker SDK. Replace **<WHEEL_PATH>** with the *full path* to your `.whl`:

```bash
pip install "<WHEEL_PATH>"
```

#### Additional Setup for Linux and macOS
* Download the Spinnaker SDK package for your system [here](https://flir.app.boxcn.net/v/SpinnakerSDK)
* Follow the installation instructions in the README
* Install the Python bindings found alongside the SDK package

### Running Parallax
```bash
python -m parallax
```

### Optional: Enable SuperPoint + SuperGlue Reticle Detection
Parallax supports reticle detection using SuperPoint + LightGlue.
To enable reticle detection using SuperPoint + SuperGlue, you must manually download 'SuperGluePretrainedNetwork' pretrained models.

The SuperGluePretrainedNetwork is not included in this repository and is distributed under its own licensing terms.
Please review their [license](https://github.com/magicleap/SuperGluePretrainedNetwork) before use.

Manual Setup Instructions
Clone the repository into the external/ folder in your Parallax project root:
```bash
pip install git+https://github.com/AllenNeuralDynamics/sfm.git@main
git clone https://github.com/magicleap/SuperGluePretrainedNetwork.git external/SuperGluePretrainedNetwork
```
Verify your folder structure looks like this:
```bash
parallax/
├── external/
│   └── SuperGluePretrainedNetwork/
│       └── models/
│           ├── superpoint.py
│           └── weights/
│               ├── superpoint_v1.pth
│               └── superglue_indoor.pth
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
