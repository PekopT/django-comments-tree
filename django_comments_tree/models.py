from typing import Optional, List
from dataclasses import dataclass, field

try:
    from django.contrib.postgres.aggregates import ArrayAgg

    postgres_available = True
except ImportError:
    postgres_available = False

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.core import signing
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models import Q
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from django_comments_tree.signals import comment_was_flagged
from django_comments_tree import get_structured_data_class

from django.conf import settings as djsettings
from django_comments_tree.conf import settings
from treebeard.mp_tree import MP_Node, MP_NodeManager

from .abstract import CommentAbstractModel

LIKEDIT_FLAG = "I liked it"
DISLIKEDIT_FLAG = "I disliked it"


def max_thread_level_for_content_type(content_type):
    app_model = "%s.%s" % (content_type.app_label, content_type.model)
    if app_model in settings.COMMENTS_TREE_MAX_THREAD_LEVEL_BY_APP_MODEL:
        return settings.COMMENTS_TREE_MAX_THREAD_LEVEL_BY_APP_MODEL[app_model]
    else:
        return settings.COMMENTS_TREE_MAX_THREAD_LEVEL


class MaxThreadLevelExceededException(Exception):
    def __init__(self, comment):
        self.comment = comment
        # self.max_by_app = max_thread_level_for_content_type(content_type)

    def __str__(self):
        return "Max thread level reached for comment %d" % self.comment.id


class CommentManager(MP_NodeManager):

    def _validate_assoc(self, root, association):
        if root.assoc is None:
            root.assoc = association
            root.save()

    def get_root(self, obj, site=None):
        """ Return the root for the given object """
        if site is None:
            site = Site.objects.get(pk=settings.SITE_ID)

        try:
            ct = ContentType.objects.get_for_model(obj)
            qs = CommentAssociation.objects.select_related("root")
            assoc = qs.get(
                content_type=ct,
                object_id=obj.id,
                site=site)

            self._validate_assoc(assoc.root, assoc)
            return assoc.root
        except ObjectDoesNotExist:
            return None

    def get_or_create_root(self, obj, site=None):
        """
        Retrieve the root for this object. Create if it does not exists.

        TreeComents are associated with any object in the system using
        GenericForeignKeys and a CommentAssociation object.

        This object associates the `object commented upon` with the root
        of the comments for that object. The root can then contain the TreeComments
        for that object, to a very deeply nested level if desired.

        - Or not nested at all


        :param obj:
        :param site:
        :return:
        """
        ct = ContentType.objects.get_for_model(obj)

        if site is None:
            site = Site.objects.get(pk=settings.SITE_ID)

        try:
            assoc = CommentAssociation.objects.select_related("root").get(
                content_type=ct,
                object_id=obj.id,
                site=site)
            self._validate_assoc(assoc.root, assoc)
        except ObjectDoesNotExist:
            root = TreeComment.add_root()
            assoc = CommentAssociation.objects.create(content_type=ct,
                                                      object_id=obj.id,
                                                      content_object=obj,
                                                      site=site,
                                                      root=root)
            root.assoc = assoc
            root.save()

        return assoc.root

    def create_for_object(self, obj, **kwargs):
        root = self.get_or_create_root(obj)
        return root.add_child(**kwargs)

    def in_moderation(self):
        """
        QuerySet for all comments currently in the moderation queue.
        """
        return self.get_queryset().filter(is_public=False, is_removed=False)

    def for_model(self, model, content_type=None, site=None):
        """
        QuerySet for all comments for a particular model (either an instance or
        a class).

        Optionally pass in content_type to avoid the query needed to get that for
        the model

        Returns a queryset for all comments associated with the given model.


        """
        if content_type is None:
            content_type = ContentType.objects.get_for_model(model)

        qs = self.get_queryset().filter(assoc__content_type=content_type)
        qs = qs.filter(depth__gt=1)  # Exclude root objects
        if site is not None:
            qs = qs.filter(assoc__site=site)
        if isinstance(model, models.Model):
            pk = model._get_pk_val()
            qs = qs.filter(assoc__object_id=pk)
        return qs

    def for_app_models(self, *args, **kwargs) -> Optional[models.QuerySet]:
        """Return TreeComments for pairs "app.model" given in args"""
        content_types = []
        for app_model in args:
            app, model = app_model.split(".")
            content_types.append(ContentType.objects.get(app_label=app,
                                                         model=model))
        return self.for_content_types(content_types, **kwargs)

    def for_content_types(self,
                          content_types: List[str],
                          site: int = None) -> Optional[models.QuerySet]:
        """
        Return all descendants of the content type.
        :param content_types:
        :param site:
        :return:
        """
        qs = TreeComment.objects.filter(assoc__content_type__in=content_types)
        qs = qs.filter(depth__gt=1)  # Exclude root nodes
        if site is not None:
            qs = qs.filter(assoc__site=site)

        return qs

    def count_for_content_types(self, content_types: List[str], site: int = None) -> int:
        """ Retrieve a count of comments for the given list of content types """
        qs = self.for_content_types(content_types=content_types, site=site)
        return qs.count()

    def count_for_model(self, model, site: int = None) -> int:
        """ Retrieve a count of comments for the given list of content types """

        qs = self.for_model(model=model, site=site)
        return qs.count()

    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.select_related(
            'commentassociation', 'commentassociation__content_type')
        return qs

    def user_flags_for_model(self, user, model, content_type=None):
        """
        Retrieve a summary of flags for the given user and model

        The return value is a dict with a list of comment id's that the user
        has liked, disliked and reported.

        The method returns a queryset, that should have 1 or 0 values

        Use the result like this:


        qs = user_flags_for_model(...)
        if len(qs):
            return Response(qs[0])


        NOTE: qs.first() does not work the way you want.


        """

        result = {'user': user.id, 'liked': [], 'disliked': [], 'reported': []}

        if content_type is None:
            content_type = ContentType.objects.get_for_model(model)

        qs = TreeCommentFlag.objects
        qs = qs.filter(user=user)
        qs = qs.filter(comment__assoc__content_type=content_type)
        if isinstance(model, models.Model):
            pk = model._get_pk_val()
            qs = qs.filter(comment__assoc__object_id=pk)

        if all([
            postgres_available,
            'postgres' in djsettings.DATABASES['default']['ENGINE']
        ]):
            # Okay to use postgres
            qs = qs.values('user')  # This cause a crucial "group_by"

            qs = qs.annotate(
                liked=ArrayAgg(
                    'comment__pk',
                    filter=Q(flag=LIKEDIT_FLAG)))
            qs = qs.annotate(
                disliked=ArrayAgg(
                    'comment__pk',
                    filter=Q(flag=DISLIKEDIT_FLAG)))
            qs = qs.annotate(
                reported=ArrayAgg(
                    'comment__pk',
                    filter=Q(flag=TreeCommentFlag.SUGGEST_REMOVAL)))

            if qs:
                return qs[0]
        else:
            qs = qs.values('user', 'comment', 'flag')  # This cause a crucial "group_by"
            result = {'user': user.id, 'liked': [], 'disliked': [], 'reported': []}
            mm = {LIKEDIT_FLAG: 'liked',
                  DISLIKEDIT_FLAG: 'disliked',
                  TreeCommentFlag.SUGGEST_REMOVAL: 'reported'}
            for q in qs.all():
                key = mm[q['flag']]
                result[key].append(q['comment'])

        return result


class CommentAssociation(models.Model):
    """
    Associate a tree node with a particular model by GenericForeignKey

    """

    @classmethod
    def from_db(cls, *args, **kwargs):
        """ Save original value of root so we can """
        new = super().from_db(*args, **kwargs)
        return new

    # Root of comments for the associated model
    root = models.OneToOneField('TreeComment',
                                on_delete=models.CASCADE,
                                null=True)

    # Content-object field
    content_type = models.ForeignKey(ContentType,
                                     verbose_name=_('content type'),
                                     related_name="content_type_set_for_%(class)s",
                                     on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey(ct_field="content_type", fk_field="object_id")

    # Retained a legacy. Remove once I determine it is not needed
    # object_pk = models.TextField(_('object ID'))

    # Metadata about the comment
    site = models.ForeignKey(Site, on_delete=models.CASCADE)

    @property
    def object_pk(self):
        return str(self.object_id)

    def __str__(self):
        return (f"CommentAssociation pk={self.pk} "
                f"oid={self.object_id} ct_id={self.content_type_id} root_id={self.root_id}")


@dataclass
class CommentData:
    id: int
    comment: str = ''
    comment_rendered: str = ''
    likes: int = 0
    parent_id: int = -1
    timestamp: str = ''
    depth: int = 1
    children: list = field(default_factory=list)


class TreeComment(MP_Node, CommentAbstractModel):
    """
    TreeComment MP Node

    The assoc field is an optimization that allows for database operations
    to traverse a query from a comment object to the association object and
    to the GenericForeign Key object. To query for comments for a given page,
    given the page id:

        commments = TreeComment.objects.filter(assoc__object_id=pk)

    This might assume that there are only comments for a particular type.
    If comments are associated with multiple types, you will need to query
    or cache the comment
    """
    node_order_by = ['submit_date']

    assoc = models.ForeignKey('CommentAssociation',
                              on_delete=models.SET_NULL,
                              blank=True,
                              null=True)

    def __init__(self, *args, **kwargs):
        self._association = None
        super().__init__(*args, **kwargs)

    followup = models.BooleanField(blank=True, default=False,
                                   help_text=_("Notify follow-up comments"))
    objects = CommentManager()

    def add_child(self, *args, comment=None, **kwargs):
        """
        Add a new comment.
        This can be called on a root node, or anywhere in the comment hierarchy.

        Checks for the "Global" maximum depth here. There is also a check for
        an object-specific maximum depth in the
        Check for maximum depth before adding child
        """
        depth = self.depth
        if depth > settings.COMMENTS_TREE_MAX_THREAD_LEVEL:
            raise MaxThreadLevelExceededException(self)

        max_level = max_thread_level_for_content_type(
            self.assoc.content_type)
        if max_level and self.thread_level > max_level:
            raise MaxThreadLevelExceededException(self)

        if 'instance' in kwargs:
            child = super().add_child(*args, **kwargs)
            if child.assoc != self.assoc:
                child.assoc = self.assoc
                child.save()
        else:
            if 'assoc' not in kwargs:
                kwargs['assoc'] = self.assoc
            child = super().add_child(*args, comment=comment, **kwargs)
        return child

    def save(self, *args, **kwargs):
        """
        Save a TreeComment
        """
        super().save(*args, **kwargs)

    def update_assoc(self):
        """ Set or update the assoc value """
        root = self.get_root()
        a = CommentAssociation.objects.get(root=root)
        if self.assoc != a:
            self.assoc = a
            self.save()

    def get_reply_url(self):
        return reverse("comments-tree-reply", kwargs={"cid": self.pk})

    def allow_thread(self):
        if self.get_depth() < max_thread_level_for_content_type(self.content_type):
            return True
        else:
            return False

    @property
    def thread_level(self):
        """ Calculate thread level from depth

        The root object has a depth of 1, so thread_level is depth -1
        """
        return self.depth - 1

    @property
    def association(self):
        """
        Return the content type for this comment. We have to search from the root for this.
        Cache the value though.
        """
        if self.assoc is None:
            root = self if self.is_root() else self.get_root()
            qs = CommentAssociation.objects.select_related('content_type')
            self.assoc = qs.get(root=root)

        return self.assoc

    @property
    def content_type(self):
        """
        Return the content type for this comment. We have to search from the root for this.
        Cache the value though.
        """
        assoc = self.association
        if assoc:
            return assoc.content_type

        return None

    @property
    def object_id(self):
        """ Accessor added for compatibility with django_contrib.comments """
        assoc = self.association
        if assoc:
            return assoc.object_id

        return None

    @property
    def content_object(self):
        """ Get and return the object associated with this comment stream """
        assoc = self.association
        if assoc:
            ct = assoc.content_type
            try:
                return ct.get_object_for_this_type(
                    pk=assoc.object_id)
            except ObjectDoesNotExist:
                pass

        return None

    @property
    def site(self):
        """ Accessor added for compatibility with django_contrib.comments """
        assoc = self.association
        if assoc:
            return assoc.site

        return None

    @classmethod
    def structured_tree_data_for_queryset(cls, queryset, annotate_cb=None):
        """
        Take an existing queryset of descendants, and convert to a json structure
        :param queryset:
        :param annotate_cb: Function - receives the comment and data, so that the calling
        code can add additional values to the data. For example, accessing the user.profile.
        This code cannot do that since it does not have visibility to the profile (if it exists)
        :return:
        """

        # Build a path lookup table
        # Faster than using node.get_parent(), which can cause another query
        path_to_node = {c.path: c for c in queryset}

        def parent_id_for(cnode):
            basepath = cnode._get_basepath(cnode.path, cnode.depth - 1)
            if basepath in path_to_node:
                return path_to_node.get(basepath).id
            return None

        # Now I can build the data structure directly
        flat_data = []
        by_id = {}
        details_by_id = {}  # Store data that I don't want to send to client
        for c in queryset:
            data = get_structured_data_class()(
                id=c.id,
                comment=c.comment.raw,
                comment_rendered=c.comment.rendered,
                parent_id=parent_id_for(c),
                depth=c.depth - 1,
            )

            if annotate_cb:
                data = annotate_cb(c, data)
            flat_data.append(data)
            by_id[c.id] = data
            details_by_id[c.id] = {
                'path': c.path,
                'depth': c.depth,
            }

        if queryset.count() == 0:
            return {'comments': []}

        # Now, build the tree structure... a bit trickier
        steplen = queryset[0].steplen

        def get_child_ids(node):
            details = details_by_id.get(node.id)
            path = details.get("path")
            depth = details.get("depth")
            keys = [k for k in path_to_node.keys()
                    if (not path or k.startswith(path))
                    and len(k) / steplen == depth + 1]

            return [path_to_node[k].id for k in keys]

        for node in flat_data:
            node.children = get_child_ids(node)

        return {'comments': flat_data}

    @classmethod
    def structured_tree_data(cls, root,
                             filter_public=True,
                             start=None,
                             end=None,
                             max_depth=None):
        """
        Return a recursive structure with comments and their children,
        starting at the given root.
        """
        nodes = root.get_descendants().order_by('submit_date')

        if filter_public:
            nodes = nodes.filter(is_public=True)

        flt = Q()
        if start:
            flt = flt & Q(updated_on__gt=start)
        if end:
            flt = flt & Q(updated_on__lt=end)

        nodes = nodes.filter(flt)

        return TreeComment.structured_tree_data_for_queryset(nodes)

    @classmethod
    def tree_from_comment(cls, root,
                          filter_public=True,
                          start=None,
                          end=None,
                          max_depth=None):
        """
        Return a recursive structure with comments and their children,
        starting at the given root.
        """
        print(f"Current Depth: {root.depth}")
        retval = []
        children = root.get_children().order_by('submit_date')
        if filter_public:
            children = children.filter(is_public=True)

        if start:
            time_range = Q(updated_on__gt=start)
            if end:
                time_range = time_range & Q(updated_on__lt=end)
            children = children.filter(time_range)
        for child in children:
            if (child.numchild > 0
                    and (max_depth is None or root.depth > max_depth)):
                my_children = cls.tree_from_comment(
                    child,
                    filter_public=filter_public,
                    start=start,
                    end=end,
                    max_depth=max_depth
                )
            else:
                my_children = []
            data = {
                "comment": child,
                "children": my_children
            }

            retval.append(data)
        return retval

    @classmethod
    def tree_for_associated_object(cls, obj,
                                   with_flagging=False,
                                   with_feedback=False,
                                   user=None):

        root = TreeComment.objects.get_or_create_root(obj)
        data = cls.tree_from_comment(root)
        return data

    def users_flagging(self, flag):
        return [obj.user for obj in self.flags.filter(flag=flag)]


@receiver(comment_was_flagged)
def unpublish_nested_comments_on_removal_flag(sender, comment, flag, **kwargs):
    if flag.flag == TreeCommentFlag.MODERATOR_DELETION:
        comment.get_descendants().update(is_public=False)


class DummyDefaultManager:
    """
    Dummy Manager to mock django's CommentForm.check_for_duplicate method.
    """

    def __getattr__(self, name):
        return lambda *args, **kwargs: []

    def using(self, *args, **kwargs):
        return self


class TmpTreeComment(dict):
    """
    Temporary TreeComment to be pickled, zipped and appended to a URL.
    """
    _default_manager = DummyDefaultManager()

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            if self.get('tree_comment'):
                try:
                    return getattr(self.get('tree_comment'), key)
                except KeyError:
                    pass
                except Exception:
                    pass
            return None

    def __setattr__(self, key, value):
        self[key] = value

    def save(self, *args, **kwargs):
        pass

    def _get_pk_val(self):
        if self.tree_comment:
            return self.tree_comment._get_pk_val()
        else:
            content_type = "%s.%s" % self.content_type.natural_key()
            return signing.dumps("%s:%s" % (content_type, self.object_id))

    def __setstate__(self, state):
        ct_key = state.pop('content_type_key')
        ctype = ContentType.objects.get_by_natural_key(*ct_key)
        self.update(
            state,
            content_type=ctype,
            content_object=ctype.get_object_for_this_type(
                pk=state['object_id']
            )
        )

    def __reduce__(self):
        state = {k: v for k, v in self.items() if k != 'content_object'}
        ct = state.pop('content_type')
        state['content_type_key'] = ct.natural_key()
        return (TmpTreeComment, (), state,)


# ----------------------------------------------------------------------
class BlackListedDomain(models.Model):
    """
    A blacklisted domain from which comments should be discarded.
    Automatically populated with a small amount of spamming domains,
    gathered from http://www.joewein.net/spam/blacklist.htm

    You can download for free a recent version of the list, and subscribe
    to get notified on changes. Changes can be fetched with rsync for a
    small fee (check their conditions, or use any other Spam filter).
    """
    domain = models.CharField(max_length=200, db_index=True)

    def __str__(self):
        return self.domain

    class Meta:
        ordering = ('domain',)


class TreeCommentFlag(models.Model):
    """
    Records a flag on a comment. This is intentionally flexible; right now, a
    flag could be:

        * A "removal suggestion" -- where a user suggests a comment for (potential) removal.

        * A "moderator deletion" -- used when a moderator deletes a comment.

    You can (ab)use this model to add other flags, if needed. However, by
    design users are only allowed to flag a comment with a given flag once;
    if you want rating look elsewhere.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_('user'),
        related_name="treecomment_flags",
        on_delete=models.CASCADE,
    )
    comment = models.ForeignKey(
        # Translators: 'comment' is a noun here.
        TreeComment,
        verbose_name=_('comment'),
        related_name="flags",
        on_delete=models.CASCADE,
    )
    # Translators: 'flag' is a noun here.
    flag = models.CharField(_('flag'), max_length=30, db_index=True)
    flag_date = models.DateTimeField(_('date'), default=None)

    # Constants for flag types
    SUGGEST_REMOVAL = "removal suggestion"
    MODERATOR_DELETION = "moderator deletion"

    MODERATOR_APPROVAL = "moderator approval"

    class Meta:
        unique_together = [('user', 'comment', 'flag')]
        verbose_name = _('comment flag')
        verbose_name_plural = _('comment flags')

    def __str__(self):
        return "%s flag of comment ID %s by %s" % (
            self.flag, self.comment_id, self.user.get_username()
        )

    def save(self, *args, **kwargs):
        if self.flag_date is None:
            self.flag_date = timezone.now()
        super().save(*args, **kwargs)
