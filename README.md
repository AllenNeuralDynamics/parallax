# Parallax

## GUI software for photogrammetry-assisted probe targeting in electrophysiology

### Dependencies
* python3-pyqt5
* python3-numpy
* python3-scipy
* python3-opencv
* python-newscale
* spinnaker-python

### Installation via `conda`

First, clone the this repository.

Then, browse to the top-level `parallax` code directory and run:

```bash
conda env create --file environment.yml
```

This will create a new `conda` environment called `parallax`.

To activate the environment and launch the GUI, run:

```bash
conda activate parallax
python src/main.py
```

