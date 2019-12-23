from django.conf.urls import url
from django.contrib.contenttypes.views import shortcut
from rest_framework.urlpatterns import format_suffix_patterns

from django_comments_tree import api
from .views.comments import (comment_done, confirm, dislike, dislike_done,
                             FlagView, like, like_done, mute, post_comment,
                             reply, sent)
from .views.moderation import (approve, approve_done, delete, delete_done,
                               flag, flag_done)

urlpatterns = [
    url(r'^sent/$', sent, name='comments-tree-sent'),
    url(r'^confirm/(?P<key>[^/]+)/$', confirm,
        name='comments-tree-confirm'),
    url(r'^mute/(?P<key>[^/]+)/$', mute, name='comments-tree-mute'),
    url(r'^reply/(?P<cid>[\d]+)/$', reply, name='comments-tree-reply'),

    # Remap comments-flag to check allow-flagging is enabled.
    url(r'^flag/(\d+)/$', FlagView.as_view(), name='comments-flag'),
    # New flags in addition to those provided by django-contrib-comments.
    url(r'^like/(\d+)/$', like, name='comments-tree-like'),
    url(r'^liked/$', like_done, name='comments-tree-like-done'),
    url(r'^dislike/(\d+)/$', dislike, name='comments-tree-dislike'),
    url(r'^disliked/$', dislike_done, name='comments-tree-dislike-done'),

    # API handlers.
    url(r'^api/comment/$', api.CommentCreate.as_view(),
        name='comments-tree-api-create'),
    url(r'^api/(?P<content_type>\w+[-\.]{1}\w+)/(?P<object_pk>[-\w]+)/$',
        api.CommentList.as_view(), name='comments-tree-api-list'),
    url(r'^api/(?P<content_type>\w+[-\.]{1}\w+)/(?P<object_pk>[-\w]+)/count/$',
        api.CommentCount.as_view(), name='comments-tree-api-count'),
    url(r'^api/feedback/$', api.ToggleFeedbackFlag.as_view(),
        name='comments-tree-api-feedback'),
    url(r'^api/flag/$', api.CreateReportFlag.as_view(),
        name='comments-tree-api-flag'),
    url(r'^api/flag/(?P<pk>\d+)/$', api.RemoveReportFlag.as_view(),
        name='comments-tree-api-remove-flag'),
]

# Migrated from original django-contrib-comments
urlpatterns += [
    url(r'^post/$', post_comment, name='comments-post-comment'),
    url(r'^posted/$', comment_done, name='comments-comment-done'),
    url(r'^flag/(\d+)/$', flag, name='comments-flag'),
    url(r'^flagged/$', flag_done, name='comments-flag-done'),
    url(r'^delete/(\d+)/$', delete, name='comments-delete'),
    url(r'^deleted/$', delete_done, name='comments-delete-done'),
    url(r'^approve/(\d+)/$', approve, name='comments-approve'),
    url(r'^approved/$', approve_done, name='comments-approve-done'),

    url(r'^cr/(\d+)/(.+)/$', shortcut, name='comments-url-redirect'),
]

urlpatterns = format_suffix_patterns(urlpatterns)
