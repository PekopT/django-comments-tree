from __future__ import unicode_literals
from django.conf import settings
import markdown
from django_comments_tree.render import render_draftjs, render_plain

# Default application namespace
COMMENT_URL_NAMESPACE = 'treecomments'

COMMENT_MAX_LENGTH = 3000

# Extra key to salt the TreeCommentForm.
COMMENTS_TREE_SALT = b""

# Whether comment posts should be confirmed by email.
COMMENTS_TREE_CONFIRM_EMAIL = True

# From email address.
COMMENTS_TREE_FROM_EMAIL = settings.DEFAULT_FROM_EMAIL

# Contact email address.
COMMENTS_TREE_CONTACT_EMAIL = settings.DEFAULT_FROM_EMAIL

# Maximum Thread Level.
COMMENTS_TREE_MAX_THREAD_LEVEL = 0

COMMENTS_TREE_MAX_THREAD_LEVEL_ALLOW_ANSWERS_ON_MAXIMUM_LEVEL = False

# Maximum Thread Level per app.model basis.
COMMENTS_TREE_MAX_THREAD_LEVEL_BY_APP_MODEL = {}

# Default order to list comments in.
COMMENTS_TREE_LIST_ORDER = ('submit_date',)

# Form class to use.
COMMENTS_TREE_FORM_CLASS = "django_comments_tree.forms.TreeCommentForm"

# Structured Data.
COMMENTS_TREE_STRUCTURED_DATA_CLASS = "django_comments_tree.models.CommentData"

# Model to use.
COMMENTS_TREE_MODEL = "django_comments_tree.models.TreeComment"

# Send HTML emails.
COMMENTS_TREE_SEND_HTML_EMAIL = True

# Whether to send emails in separate threads or use the regular method.
# Set it to False to use a third-party app like django-celery-email or
# your own celery app.
COMMENTS_TREE_THREADED_EMAILS = True

# Define what commenting features a pair app_label.model can have.
# TODO: Put django-comments-tree settings under a dictionary, and merge
#       COMMENTS_TREE_MAX_THREAD_LEVEL_BY_APP_MODEL with this one.
COMMENTS_TREE_APP_MODEL_OPTIONS = {
    'default': {
        'allow_flagging': False,
        'allow_feedback': False,
        'show_feedback': False,
    }
}


# Define a function to return the user representation. Used by
# the web API to represent user strings in response objects.
def username(u):
    return u.username


COMMENTS_TREE_API_USER_REPR = username

COMMENTS_TREE_API_USER_URL_REPR = username

# Set to true to enable Firebase notifications
COMMENTS_TREE_ENABLE_FIREBASE = False

COMMENTS_TREE_FIREBASE_KEY = None

# Default types we can use for comments
MARKUP_FIELD_TYPES = (
    ('plain', render_plain),
    ('markdown', markdown.markdown),
    ('draftjs', render_draftjs),
)

COMMENTS_TREE_API_USER_AVATAR_FIELD = False
COMMENTS_TREE_API_USER_AVATAR_DEFAULT = False

COMMENTS_TREE_API_USER_RANK_FIELD = False
COMMENTS_TREE_API_USER_RANK_DEFAULT = False

COMMENTS_TREE_API_ANSWER_WITH_READ_SERIALIZER = False


