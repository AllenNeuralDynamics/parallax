# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
import os
import sys
from datetime import date
from docutils.parsers.rst import roles
from docutils import nodes

sys.path.insert(0, os.path.abspath('../../'))

INSTITUTE_NAME = "Allen Institute for Neural Dynamics"

project = 'Parallax'
current_year = date.today().year
copyright = f"{current_year}, {INSTITUTE_NAME}"
author = INSTITUTE_NAME
release = "0.0.1" # Automatically set version from parallax package

autosummary_generate = True # Automatically generate stub files for autosummary
autoclass_content = "both"
autodoc_default_options = {
    'private-members': True,   # Include private members
}

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autosummary',
    "sphinx.ext.viewcode",
    "sphinx.ext.autodoc",
    "sphinx.ext.todo",
    "sphinxcontrib.video"
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'furo'
html_static_path = ['_static']
html_title = project
html_favicon = "_static/favicon.ico"
html_theme_options = {
    "light_logo": "light-logo.svg",
    "dark_logo": "dark-logo.svg",
    "source_repository": "https://github.com/AllenNeuralDynamics/parallax/",
    "source_branch": "main",
    "source_directory": "docs/source/",
}


# Custom reStructuredText (reST),
def color_role(name, rawtext, text, lineno, inliner, options={}, content=[], color=None):
    node = nodes.literal(rawtext, text, classes=[color])
    return [node], []

def red_role(name, rawtext, text, lineno, inliner, options={}, content=[]):
    return color_role(name, rawtext, text, lineno, inliner, options, content, color='red')

def yellow_role(name, rawtext, text, lineno, inliner, options={}, content=[]):
    return color_role(name, rawtext, text, lineno, inliner, options, content, color='yellow')

def blue_role(name, rawtext, text, lineno, inliner, options={}, content=[]):
    return color_role(name, rawtext, text, lineno, inliner, options, content, color='blue')

roles.register_local_role('red', red_role)
roles.register_local_role('yellow', yellow_role)
roles.register_local_role('blue', blue_role)

html_static_path = ['_static'] 
html_css_files = [
    'custom.css',
]