# Configuration file for the Sphinx documentation builder.Configuration file for the
# Sphinx documentation builder.

# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

project = "aqueue"
author = "Tim Martin"
copyright = "2022, Tim Martin"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
]

html_theme = "furo"
html_static_path = ["_static"]

autodoc_default_options = {
    "member-order": "bysource",
}

intersphinx_mapping = {
    "https://docs.python.org/3": None,
}


# allow cross-referencing without a specific role
default_role = "any"
