# Parallax

## GUI software for photogrammetry-assisted probe targeting in electrophysiology

### Installation via `conda`

First, clone the this repository.

Then, browse to the top-level `parallax` code directory and run:

```bash
conda env create --file environment.yml
conda activate parallax
```

For Linux or Mac OS, you'll need to install PySpin manually (not required for
Windows):

* download the Spinnaker SDK package for your system
[here](https://flir.app.boxcn.net/v/SpinnakerSDK)
* follow the installation instructions in the README
* repeat this for the Python bindings (located alongside the SDK package)

To launch the GUI, run the script at the top-level of this repo:

```bash
python run-parallax.py
```

