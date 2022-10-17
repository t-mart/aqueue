.. include:: ../README.rst
   :start-after: teaser-begin
   :end-before: teaser-end


Getting Started
===============

There's two things you need to do to use aqueue:

1. Implement your `Item <#items>`_ subclasses.
2. `Start your queue <#starting-your-queue>`_ with one of those
   items.

Example
=======

.. include:: ../examples/simple.py
   :code: python

Items
=====

Items are your units of work. They can represent whatever you'd like, such as parts of a website
that you're trying to scrape: an item for the index page, for subpages, for images, etc.

Each item must be an instance of a subclass of `aqueue.Item`. Imperatively, you must implement the
`aqueue.Item.process` method, which defines the work of the item, such as making an HTTP request, parsing it,
downloading something, etc.

.. note::

  ``aqueue`` is built on top of `Trio <https://trio.readthedocs.io/en/stable/index.html>`_, and,
  therefore, you may only use Trio-compatible async primitives inside ``Item`` methods.

Fundamentally, items can make other items to be processed later. To enqueue them, use the
``enqueue`` method passed to the ``process`` method.

As a rule of thumb, you should make a new item class whenever you notice a one-to-many relationship.
For example, "this *one* page has *many* images I want to download".

.. autoclass:: aqueue.Item
   :members:

.. autodata:: aqueue.EnqueueFn

.. autodata:: aqueue.SetDescFn


Starting your queue
===================


Once you've implemented some `aqueue.Item` classes, start your queue to kick things off.

.. autofunction:: aqueue.run_queue

.. autofunction:: aqueue.async_run_queue

.. autodata:: aqueue.QueueTypeName


Sharing state
=============

Often, its beneficial to share state between the items. Using the website scrape example again, you
may want to keep track of the URLs you've visited so you don't scrape them twice.

If this is needed, simply keep a global set/dict/list and store a key for the item. For example, a
URL string may be a good key.

If you don't want to or can't use a global variable, consider a
`contextvars.ContextVar`.

Persisting state
================

During development, its probably likely that your program will crash after doing some work. For
example, maybe your HTTP request timed out or you had a bug in your HTML parsing.

It's a shame to lose that work that's been done. So, if you're looking for a really handy way to
persist state across runs, check out the built-in
`shelve` module. It's like a dict that
automatically saves to a file each time you set a key in it.

Other cool things
=================

The API is fully docstringed and type-hinted 🥳
