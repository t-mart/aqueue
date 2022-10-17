.. teaser-begin

==========
``aqueue``
==========

``aqueue`` is an async task queue with live progress display.

You put items in, and they get processed, possibly creating more items which get processed, and so
on, until all items are completed. A typical use case would be to scrape a website.

.. image:: https://raw.githubusercontent.com/t-mart/aqueue/master/docs/_static/demo.gif
  :alt: Demonstration of aqueue

.. note::

  ``aqueue``, or any asynchronous framework, is only going to be helpful if you're performing
  **I/O-bound** work.


Installation
============

``aqueue`` is a Python package `hosted on PyPI <https://pypi.org/project/aqueue/>`_. The recommended
installation method is `pip <https://pip.pypa.io/en/stable/>`_-installing into a virtual
environment:

.. code-block:: shell

   pip install aqueue

Getting Started
===============

There's two things you need to do to use aqueue:

1. Implement your `Item <https://t-mart.github.io/aqueue/#items>`_ subclasses.
2. `Start your queue <https://t-mart.github.io/aqueue/#starting-your-queue>`_ with one of those
   items.

.. teaser-end

Example
=======

If you had a hierarchy of items like this...

.. mermaid:: /docs/_static/simple.mmd

Then, you might process it with ``aqueue`` like this...

.. include:: /examples/simple.py
   :code: python

Documentation Page
==================

Visit the full documentation site at `<https://t-mart.github.io/aqueue/>`_

.. -project-information-

Project Information
===================

- **License**: `MIT <https://choosealicense.com/licenses/mit/>`_
- **PyPI**: https://pypi.org/project/aqueue/
- **Source Code**: https://github.com/t-mart/aqueue
- **Documentation**: https://t-mart.github.io/aqueue/
- **Supported Python Versions**: 3.10 and later
