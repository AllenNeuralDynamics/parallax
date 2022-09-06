# MISGUIde
## Modular Insertion System Graphical User Interface and Development Environment

### Dependencies
* python3-pyqt5
* python3-numpy
* python3-scipy
* python3-opencv
* spinnaker-python

### Installation via `conda`

First, clone the `mis-guide` repository.

Then, browse to the top-level `mis-guide` code directory and run:

```bash
conda env create --file environment.yml
```

This will create a new `conda` environment called `mis-guide`.

To activate the environment and launch the GUI, run:

```bash
conda activate mis-guide
python src/main.py
```

