import django
from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

if django.VERSION[:2] < (2, 0):
    from django.conf.urls import include, url as re_path
else:
    from django.urls import include, re_path

from django.views.i18n import JavaScriptCatalog
    
from django_comments_tree import LatestCommentFeed
from django_comments_tree.views import TreeCommentListView

from comp import views


admin.autodiscover()


urlpatterns = [
    re_path(r'^$', views.HomepageView.as_view(), name='homepage'),
    re_path(r'^i18n/', include('django.conf.urls.i18n')),
    re_path(r'^articles/', include('comp.articles.urls')),
    re_path(r'^quotes/', include('comp.extra.quotes.urls')),
    re_path(r'^comments/', include('django_comments_tree.urls')),
    re_path(r'^comments/$',
            TreeCommentListView.as_view(content_types=["articles.article",
                                                      "quotes.quote"],
                                       paginate_by=10, page_range=5),
            name='comments-tree-list'),
    re_path(r'^feeds/comments/$', LatestCommentFeed(), name='comments-feed'),    
    re_path(r'^api-auth/', include('rest_framework.urls',
                                   namespace='rest_framework')),
    re_path(r'^jsi18n/$', JavaScriptCatalog.as_view(),
            name='javascript-catalog'),
    re_path(r'admin/', admin.site.urls),    
]


if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()


if 'rosetta' in settings.INSTALLED_APPS:
    urlpatterns += [re_path(r'^rosetta/', include('rosetta.urls'))]
