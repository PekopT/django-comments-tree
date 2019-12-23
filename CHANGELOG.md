# Change Log

## [0.1.4] = 2019-12-23

    Making *-tree package works. Fixing errors

## [0.1.3] = 2019-10-27

    Add data migration to insure that the 'assoc' value is set in the TreeComments
    
## [0.1.2] = 2019-10-23

    Added a Manager method: ```user_flags_for_model```
    
    This method uses the Postgres only ArrayAgg, if Postgres is available. 
    This also required me to expand my checking so that the module can still work if postgres is
    not used. This will require some more elaborate testing in the future, if I want to test with postgres
    and without. I'll likely test locally with postgres
    
## [0.1.1] - 2019-10-23

    Added a migrations that was missed in the previous version. The migration adds the 
    Blank=True to the 'assoc' ForeignKey for TreeComments
    
    
## [0.1.0] - 2019-10-23

    Denormalized the CommentAssociation model by adding an 'assoc' into each TreeComment
    object. This is set to the association model connected to the root.
    
    Having this value on each comment enables more efficient queries when getting lists of
    comments for a particular level, or for a particular page, user, or list of content types.
    
    Converted the CommentAssociation root = ForeignKey into a OneToOneField so that the
    reverse relationship can be traversed. Now it is possible to use root.commentassociation
    
    Added select_related('commentassociation') to the main queryset so that the association
    is always returned with the root. Generally the root will need this for subsequent 
    queries, so it is best to select it whenever the root is selected.
    
    Added logic to insure that new TreeComment objects have the 'assoc' set upon creation.
    
    Added logic to update the root with the assoc value if not already set, this will insure
    that all root values have this set when queried.
    
    Expanded the tests on the  models.
    
## [0.1.0rc5] - 2019-08-11

    Add 'create' as a kw argument to save
    Used when notifying of commponet post update or add

## [0.1.0rc4] - 2019-08-10

    Notifiy signal when comments are updated.


## [0.1.0rc3] - 2019-08-07

    Officially remove python 3.6 from compatibiliy due to use of dataclasses
    Update travis.yml to test against python 3.7 and 3.8 only.
    Fix but in main.sh script

## [0.1.0rc2] - 2019-08-07

    Remove the content_type from the fields of the api serializer_

## [0.1.0rc1] - 2019-08-04

    This is the first release candidate, since I am getting
    close to putting it into producion.

    * Added a new dataclass for the comments data
    * Add mechanism to override the dataclass used
        * Provides client ability to extend and annotate
    * Added additional testing
    * Remove python 3.6 compatibility due to dataclasses

## [0.1.0b13] - 2019-08-04

    Fix a typo on dependecies

## [0.1.0b12] - 2019-08-03

    I've changed the default comment markup type to plan
    Added the plain type
    Migrated draftjs render to the project
    Improved make scripts
    Fixed tox issues with py36
    Improved the structure data code


## [0.1.0b8] - 2019-07-28

    Resolve issue with apps loading in the
    __init__.py file. the 'django apps' import
    was conflicting with the .apps.py file, and causing an error on initialization.

## [0.1.0b7] - 2019-07-18

    Add method to compute and return structured data that is tailored
    for React and redux. Added a test_queries file with some tests on
    this data.

    * Change default MAX_THREAD_LEVEL to 5
    * fixed test issues with change to thread level
        * Tests now adapt to setting, instead of being hard-coded
    * add tests to test_models to increase test coverage on models file

    Changes to models.py:
        * add property .thread_level that computes level from depth
        * add propety .content_object to retrieve content object for thread
        * Improved filtering on tree data return values.

## [0.1.0b6-1] - 2019-07-16

    Yet Another fix for pip import issue

## [0.1.0b6] - 2019-07-16

    Another fix for pip import issue

## [0.1.0b5] - 2019-07-16

    Another fix for pip import issue

## [0.1.0b4] - 2019-07-16

    Fix build error from b3

## [0.1.0b3] - 2019-07-16

    Migrate methods from __init__.py of django-contrib-comments.
    These had been missed from previous migrations.

    * change method used for version, since previous one failed on install.

    ** This version had a build error

## [0.1.0b1] - 2019-07-16

    Fully removed django-contrib-comments dependency.

    Removed the module from the list of requrements, and made
    additional changes to get the tox tests passing.


## [0.1.0a9] - 2019-07-16

    * Resolve test issues on APICommentSerializer.
    * Resolve flake8 errors on travis build

## [0.1.0a8] - 2019-07-16

    Removed remaining dependencies on django_comments.
    * Copied in a few remaining templates from django_comment
    * Migrated django_comments templatetags into this module

## [0.1.0a7] - 2019-07-15

    * Migrate all object_pk to object_id
    * Move django_comments.forms into app
    * Modify `CommentForm` to match new models
    * Add initial `APICommentSerializer
    * Remove object_id field from TreeComment and create migration
    * Migrate `CommentsAdmin` into this project
    * Update local CommentsAdmin to match fields for this project

## [0.1.0a6] - 2019-07-15

    * No code changes
    * Update how the versions are determined

## [0.1.0a5] - 2019-07-14

    * Fixed build error caused by flake8 issue

## [0.1.0a2] - 2019-07-14

    * Change development status to 3 - Alpha

## [0.1.0a1] - 2019-07-14

    * Resolve issue in models.py `add_child` to support adding from a form.
    * Add `updated_on` field to `TreeComment` model
    * Added an `init_form_data` method to TreeCommentForm that is currently unused and may be removed.


## [0.1.0] - 2019-04-11

    Revert the changes back to a pre-release version since I've forked the repo,
    changed the name, and will be replacing the core models with a new approach.

    * Renamed all django-comments-xtd (etc.) to django-comments-tree
    * Changed Author to Ed Henderson, moved @danirus to lead contributor


## [2.4.0] - 2019-02-19

    New minor release thanks to Mandeep Gill with the following changes:

    * Adds support for non-int based object_pk, for instead when using UUIDs or
      HashIds as the primary key on a model (closes #112).
    * Refactors the commentbox props generation into a separate function so can
      be used from the webapi for use with rest_framework/API-only backends that
      don't make use of server-side templates.
    * Adds a pyproject.yaml for use with `poetry` (https://poetry.eustace.io)
      and new pip environments (PEP 518).

## [2.3.1] - 2019-01-08

    * Fixes issue #116.
    * Updates package.json JavaScript dependencies:
       * babel-cli from 6.24.1 to 6.26.0.
       * jquery from 3.2.1 to 3.3.1.

## [2.3.0] - 2018-11-29

    * Upgrades Twitter-Bootstrap from v3 to v4.
    * Fixes issue with tutorial fixtures (bug #114).
    * Upgrade all JavaScript dependencies. Check packages.json for details.
      The major changes are:
       * ReactJS updates from 15.5 to 16.5.
       * Babel updates from 6 to 7.
       * Webpack from 2.4.1 to 4.21.0.
       * Bootstrap from 3.3.7 to 4.1.3.
    * Updates webpack.config.js.
    * Demo sites and tutorial have been adapted to Twitter Bootstrap v4.
    * Fixes issues #94, #108, #111.

## [2.2.1] - 2018-10-06

    * Resolves deprecation warnings and adopt recommendations in unit tests.
    * Fixes demo sites so that they work with Django 1.11, Django 2.0 and
      Django 2.1.

## [2.2.0] - 2018-08-12

    * Adds support for Django 2.1.
    * Drops support for Django < 1.11 as it depends on django-contrib-comments
      which dropped support too.
    * Fixes issue 104 (on lack of Django 2.1 support).

## [2.1.0] - 2018-02-13

    * Fixes issues #76, #86 and #87.
    * Request user name and/or email address in case the user is logged
      in but the user's email attribute is empty and/or the user's
      get_full_name() method returns an empty string.

## [2.0.10] - 2018-01-19

	* Adds Django 2.0 compatibility.
	* Fixes issues #81 and #83.
	* Replaces the use of django.test.client by RequestFactory in unittests.

## [2.0.9] - 2017-11-09

	* Fix issue 77. Template filter tree_comment_gravatar_url must not
	  hard-code http schema in URL (reported by @pamost).

## [2.0.8] - 2017-09-24

	* App translation to Finnish, thanks to Tero Tikkanen (@terotic).

## [2.0.7] - 2017-09-20

	* Adds missing migration for a field's label (issue 71).
	* Makes the form label for field 'name' translatable (issue 73).

## [2.0.6] - 2017-08-08

	* Code fixes to enable proper support for the Django Sites Framework.
	* Code fixes for the `comp` demo site.
	* Makes demo site dates in initial data files timezone aware.
	* Improves documentation on setting up demo sites.
	* Style changes in CSS wells.

## [2.0.5] - 2017-07-20

	* Surpass version number to fix problem with package upload in PyPI.
	* No changes applied to this version.

## [2.0.4] - 2017-07-19

	* Use `django.core.signing` with temporary comment passed in URL
	  redirection.
	* Fix mistakes in documentation.

## [2.0.3] - 2017-07-10

	* App translation to French thanks to Brice Gelineau.
	* Fixed MANIFEST.in file, so that files with translations are
	  distributed.

## [2.0.0] - 2017-06-04

	* Javascript plugin (based on ReactJS).
	* Web API to:
	  * Create a comment for a given content type and object ID.
	  * List comments for a given content type and object ID.
	  * Send feedback flags (like/dislike) on comments.
	  * Send report flag (removal suggestion) for a comment.
	  * Template filter `has_permission` applicable to a user object and
	    accepting a string specifying the `app_label.permission` being
	    checked. It returns `True` if the user has the given permission,
	    otherwise returns False.
	* Setting `COMMENTS_XTD_API_USER_REPR` defines a lambda function to
	  return the user string representation used by the web API in response
	  objects.
	* Setting `COMMENTS_XTD_APP_MODEL_PERMISSIONS` to explicitly define what
	  commenting features are enabled on per app.model basis.
	* Templates `comments/delete.html` and `comments/deleted.html` matching
	  django-comments-tree default twitter-bootstrap styling.
	* Dependencies on Python packages: djangorestframework.
	* Supports i18n for English and Spanish.
	* All settings namespaced inside the COMMENTS_XTD setting.
	* Management command to migrate comments from django-contrib-comments to
	  django-comments-tree.
	* Enable removal link in `django_comments_tree/comment_tree.html` when the
	  user has the permission `django_comments.can_moderate`.
	* Changed, when the user logged has `django_comments.can_moderate` permission,
	  template `django_comments_tree/comment_tree.html` will show the number of
	  removal suggestions a comment has received.
	* Changed, when a comment is marked as removed by a moderator
	  (using django-comments' `comments-delete` url) every nested comment below
	  the one removed is unpublished (`is_public` attribute is turned to
	  `False`).
	* Changed view helper functions, `perform_like` and `perform_dislike` now
	  returns a boolean indicating whether a flag was created. If `True` the flag
	  has been created. If `False` the flag has been deleted. These two functions
	  behave as toggle functions.
	* Changed templates `comments/preview.html`, `comments/flag.html` and
	  `comments/flagged.hml`.
	* Removed dependency on django-markup.
	* Removed template filter `render_markup_comment`.
	* Removed setting `MARKUP_FALLBACK_FILTER`.
