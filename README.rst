django-comments-tree |TravisCI|_
===================

.. |TravisCI| image:: https://secure.travis-ci.org/sharpertool/django-comments-tree.png?branch=master
.. _TravisCI: https://travis-ci.org/sharpertool/django-comments-tree

A Django pluggable application that adds comments to your project.

.. image:: https://github.com/sharpertool/django-comments-tree/blob/master/docs/images/cover.png
  
It extends the once official `django-contrib-comments <https://pypi.python.org/pypi/django-contrib-comments>`_ with the following features:

#. Comments model based on `django-treebeard <https://pypi.python.org/pypi/django-treebeard>`_ to provide a robust and fast threaded and nested comment structure.
#. Efficiently associate a comment tree with any model through a link table which avoids populating each comment with extra link data.
#. Customizable maximum thread level, either for all models or on a per app.model basis.
#. Optional notifications on follow-up comments via email.
#. Mute links to allow cancellation of follow-up notifications.
#. Comment confirmation via email when users are not authenticated.
#. Comments hit the database only after they have been confirmed.
#. Registered users can like/dislike comments and can suggest comments removal.
#. Template tags to list/render the last N comments posted to any given list of app.model pairs.
#. Emails sent through threads (can be disable to allow other solutions, like a Celery app).
#. Fully functional JavaScript plugin using ReactJS, jQuery, Bootstrap, Remarkable and MD5.

Example sites and tests work under officially Django `supported versions <https://www.djangoproject.com/download/#supported-versions>`_:

* Django 2.2, 2.1, 2.0 and 1.11
* Python 3.6, 3.5, 3.4, 3.2 and 2.7

Additional Dependencies:

* django-contrib-comments >=1.8, <1.9
* djangorestframework >=3.8, <3.9

Checkout the Docker image `danirus/django-comments-tree-demo <https://hub.docker.com/r/danirus/django-comments-tree-demo/>`_.
  
`Read The Docs <http://readthedocs.org/docs/django-comments-tree/>`_.

Why Create a New Package
===================

I did not particularly like how the core django-contrib-comments added a GenericForeignKey to each and every comment in order to associate a comment stream with another model. I wanted to have a single place where this association was made.

I opted to add a model just for linking the comments to other models. This model has a single record for a model -> comment-tree association. The record contains the GenericForeignKey, and a single ForeignKey to the comments root node that starts the comments for that model. This is very flexible, and if the underlying model changes, it is a simple matter to move all comments to a new parent. Treebeard just makes all of this work.

Treebeard provides robust mechanisms to get the parent, children, siblings, and any other association you might needed from the comment stream. This also makes it much easier to have a very robust tree structure, so nesting, replies, replies to replies, etc. are easy to handle, and very efficient.

Attribution
===================
This package is a fork of the excellent work at `django-comments-xtd <https://github.com/danirus/django-comments-xtd>`_

I created the fork because I wanted to a comment tree based on MP_node from `django-treebeard <https://pypi.python.org/pypi/django-treebeard>`_. I consider this to be a more robust tree implementation. Treebeard suppports multiple root nodes, so each root node can be an entire comment tree.

