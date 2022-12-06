# Parallax

## GUI software for photogrammetry-assisted probe targeting in electrophysiology

### Installation via `conda`

First, clone the this repository.

Then, browse to the top-level `parallax` code directory and run:

```bash
conda env create --file environment.yml
conda activate parallax
```

You will also need to install
[python-newscale](https://github.com/AllenNeuralDynamics/python-newscale). Do
this from within the conda environment you just activated:


```bash
git clone github.com/AllenNeuralDynamics/python-newscale
cd python-newscale
pip install -e .
cd ..
```

To launch the GUI, run the script at the top-level of this repo:

```bash
python run-parallax.py
```

