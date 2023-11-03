# Parallax

## GUI software for photogrammetry-assisted probe targeting in electrophysiology
Parallax is an graphical user interface designed to aid researchers in the field of electrophysiology. With its photogrammetry-assisted targeting system, Parallax streamlines the process of probe placement, increasing accuracy and efficiency in experimental setups.


### Features
- Easy-to-use graphical interface for precise probe positioning.
- Photogrammetry assistance for enhanced targeting accuracy.
- Compatible with various electrophysiology instruments.


### Prerequisites
- Python >=3.8 (Recommended to install via [Anaconda](https://www.anaconda.com/products/individual) or [Miniconda](https://docs.conda.io/en/latest/miniconda.html))
- PySpin (for Linux or Mac OS users)


### Installation
1. Clone the repository:
```bash
git clone https://github.com/AllenNeuralDynamics/parallax.git
cd parallax
```

2. Create virtual environment and activate it:
- On Windows:
```bash
python -m venv venv
./venv/Scripts/activate
```
- On Linux/Mac:
```bash
python -m venv venv
source venv/bin/activate
```

3. Install Dependencies:
```bash
pip install .
```

### Running Parallax
```bash
python run-parallax.py
```

### Additional Setup for Linux and Mac OS
For Linux or Mac OS, you'll need to install PySpin manually (not required for
Windows):
* download the Spinnaker SDK package for your system from [here](https://flir.app.boxcn.net/v/SpinnakerSDK)
* follow the installation instructions in the README
* Install the Python bindings found alongside the SDK package

### Support and Contribution
If you encounter any issues or would like to contribute to the project, please check out our issues page on GitHub.

### License
Parallax is licensed under the Allen Institute Software License. For more details, see the LICENSE file.
