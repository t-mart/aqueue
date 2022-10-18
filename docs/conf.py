# Configuration file for the Sphinx documentation builder.Configuration file for the
# Sphinx documentation builder.

# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

from importlib.metadata import version as get_version

project = "aqueue"
author = "Tim Martin"
copyright = "2022, Tim Martin"
version = release = get_version('aqueue')

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinxcontrib.mermaid",
    "sphinx_autodoc_typehints",
]

html_theme = "furo"
html_static_path = ["_static"]

autodoc_default_options = {
    "member-order": "bysource",
}

intersphinx_mapping = {
    "https://docs.python.org/3": None,
    "https://trio.readthedocs.io/en/stable/": None,
    "https://anyio.readthedocs.io/en/stable/": None,
}

# allow cross-referencing without a specific role
default_role = "any"
