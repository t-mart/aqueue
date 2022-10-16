.. include:: ../README.rst
   :start-after: teaser-begin
   :end-before: teaser-end




Items
=====

Items are your units of work. They can represent whatever you'd like, such as parts of a website
that you're trying to scrape: an item for the index page, for subpages, for images, etc.

Each item must be an instance of a subclass of ``aqueue.Item``.

As a rule of thumb, you should make a new item class whenever you notice a one-to-many relationship.
For example, this *one* page has *many* images I want to download.

.. note::

  ``aqueue`` is built on top of `Trio <https://trio.readthedocs.io/en/stable/index.html>`_, and,
  therefore, you may only use Trio-compatible primitives inside ``Item`` methods.

.. autoclass:: aqueue.Item
   :members: process, after_children_processed, track_overall, priority, parent



.. toctree::
   :maxdepth: 2
   :caption: Contents:



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`