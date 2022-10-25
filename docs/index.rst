.. include:: ../README.rst
   :start-after: teaser-begin
   :end-before: teaser-end

Example
=======

If you had a hierarchy of items like this...


.. image:: _static/simple-diagram.png
  :alt: Simple item hierarchy with one root item and many children items stemming from it.

Then, you might process it with ``aqueue`` like this...

.. include:: ../examples/simple.py
   :code: python

Items
=====

Items are your units of work. They can represent whatever you'd like, such as parts of a website
that you're trying to scrape: an item for the index page, for subpages, for images, etc.

Each item must be an instance of a subclass of `aqueue.Item`. Imperatively, you must implement the
`aqueue.Item.process` method, which defines the work of the item, such as making an HTTP request,
parsing it, downloading something, etc.

Items can make other items to be processed later. To enqueue them, ``yield`` them from the process
method.

As a rule of thumb, you should make a new item class whenever you notice a one-to-many relationship.
For example, "this *one* page has *many* images I want to download".

.. autoclass:: aqueue.Item
   :members:

.. autodata:: aqueue.ProcessRetVal


Starting your queue
===================

Once you've implemented some `aqueue.Item` classes, start your queue to kick things off.

.. autofunction:: aqueue.run_queue

.. autofunction:: aqueue.async_run_queue

.. autodata:: aqueue.Ordering


Sharing state
=============

Often, its beneficial to share state between the items. Using the website scrape example again, you
may want to keep track of the URLs you've visited so you don't scrape them twice.

If this is needed, simply keep an object at the global or class level and store a key for the item.
For example, a URL string may be a good key.

.. code-block:: python

   import aqueue

   class MyItem(aqueue.Item):

      visited_urls = set()

      def __init__(self, url):
         self.url = url

      async def process(self):
            if self.url in self.visited_urls:
               return
            else:
               ... # do work
               self.visited_urls.add(self.url)

   aqueue.run_queue(
      initial_items=[MyItem()],
   )

If you don't want to or can't use a global variable, consider a `contextvars.ContextVar`.

Persisting state
================

During development, its probably likely that your program will crash after doing some work. For
example, maybe your HTTP request timed out or you had a bug in your HTML parsing. It's a shame to lose that work that's been done.

If you're looking for a really handy way to persist state across runs, check out the built-in
`shelve` module. It's like a dict that automatically saves to a file each time you set a key in it.

.. code-block:: python

   import aqueue, shelve

   SHELF = shelve.open('my-shelf')

   class MyItem(aqueue.Item):
      def __init__(self, url):
         self.url = url

      async def process(self):
            if self.url in SHELF:
               return
            else:
               ... # do work
               SHELF[self.url] = True

   asyncio.run(aqueue.run_queue(
      initial_items=[MyItem()],
   ))
   SHELF.close()

Otherwise, database inserts, manual file saving, etc are are fair game.

Other cool things
=================

The API is fully docstringed and type-hinted 🥳

.. include:: ../README.rst
   :start-after: -project-information-

.. toctree::