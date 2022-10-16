.. teaser-begin

==========
``aqueue``
==========

``aqueue`` is an async queue with live progress display.

.. image:: _static/demo.gif
  :alt: Demonstration of aqueue

.. note::

  ``aqueue``, or any asynchronous framework, is only going to be helpful if you're performing
  **I/O-bound** work.


Installation
============

``aqueue`` is a Python package `hosted on PyPI <https://pypi.org/project/attrs/>`_. The recommended
installation method is `pip <https://pip.pypa.io/en/stable/>`_-installing into a virtual
environment:

.. code-block:: shell

   pip install aqueue


Getting Started
===============

There's two things you need to do to use aqueue:

1. Implement your `Item <#items>`_ subclasses.
2. `Start your queue <#starting-your-queue>`_ with one of those items.

Example
=======

.. include:: ../examples/simple.py
   :code: python

.. teaser-end

Documentation Page
==================

Visit the full documentation site at `<aqueue.readthedocs.io>`_
