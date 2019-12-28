from __future__ import unicode_literals

import six
from django import http
from django.apps import apps
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.shortcuts import get_current_site
from django.core import signing
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.template import loader
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.html import escape
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from django.views.generic import ListView, View

from django_comments_tree import (comment_was_posted, get_form,
                                  get_model as get_comment_model,
                                  signals, signed)
from django_comments_tree.conf import settings
from django_comments_tree.models import (DISLIKEDIT_FLAG, LIKEDIT_FLAG,
                                         MaxThreadLevelExceededException,
                                         TmpTreeComment, TreeCommentFlag)
from django_comments_tree.utils import has_app_model_option, send_mail
from django_comments_tree.views.moderation import perform_flag
from django_comments_tree.views.utils import confirmation_view, next_redirect

TreeComment = get_comment_model()


def get_moderated_tmpl(cmt):
    return [
        "django_comments_tree/%s/%s/moderated.html" % (
            cmt.content_type.app_label, cmt.content_type.model),
        "django_comments_tree/%s/moderated.html" % cmt.content_type.app_label,
        "django_comments_tree/moderated.html"
    ]


def send_email_confirmation_request(
        comment, key, site,
        text_template="django_comments_tree/email_confirmation_request.txt",
        html_template="django_comments_tree/email_confirmation_request.html"):
    """Send email requesting comment confirmation"""
    subject = _("comment confirmation request")
    confirmation_url = reverse("comments-tree-confirm",
                               args=[key.decode('utf-8')])
    message_context = {'comment': comment,
                       'confirmation_url': confirmation_url,
                       'contact': settings.COMMENTS_TREE_CONTACT_EMAIL,
                       'site': site}
    # prepare text message
    text_message_template = loader.get_template(text_template)
    text_message = text_message_template.render(message_context)
    if settings.COMMENTS_TREE_SEND_HTML_EMAIL:
        # prepare html message
        html_message_template = loader.get_template(html_template)
        html_message = html_message_template.render(message_context)
    else:
        html_message = None

    send_mail(subject, text_message, settings.COMMENTS_TREE_FROM_EMAIL,
              [comment.user_email, ], html=html_message)


def _comment_exists(comment):
    """
    True if exists a TreeComment with same user_name, user_email and submit_date.
    """
    return (TreeComment.objects.filter(
        user_name=comment.user_name,
        user_email=comment.user_email,
        followup=comment.followup,
        submit_date=comment.submit_date
    ).count() > 0)


def _create_comment(tmp_comment):
    """
    Creates a TreeComment from a TmpTreeComment.
    """
    tmp_comment.pop('content_type')
    content_object = tmp_comment.pop('content_object')
    tmp_comment.pop('object_id')
    tmp_comment.pop('site_id')
    reply_to = tmp_comment.pop('reply_to', None)

    if reply_to:
        root = TreeComment.objects.get(pk=reply_to)
        if settings.COMMENTS_ALLOW_MAX_THREAD_LEVEL and root.depth > settings.COMMENTS_TREE_MAX_THREAD_LEVEL:
            root = root.get_parent()
    else:
        root = TreeComment.objects.get_or_create_root(content_object)

    comment = root.add_child(**tmp_comment)
    # comment = TreeComment(**tmp_comment)
    # comment.is_public = True
    comment.save()
    return comment


def on_comment_was_posted(sender, comment, request, **kwargs):
    """
    Post the comment if a user is authenticated or send a confirmation email.

    On signal django_comments.signals.comment_was_posted check if the
    user is authenticated or if settings.COMMENTS_TREE_CONFIRM_EMAIL is False.
    In both cases will post the comment. Otherwise will send a confirmation
    email to the person who posted the comment.
    """
    if settings.COMMENTS_APP != "django_comments_tree":
        return False
    if comment.user:
        user_is_authenticated = comment.user.is_authenticated
    else:
        user_is_authenticated = False

    if not settings.COMMENTS_TREE_CONFIRM_EMAIL or user_is_authenticated:
        if not _comment_exists(comment):
            new_comment = _create_comment(comment)
            comment.tree_comment = new_comment
            signals.confirmation_received.send(sender=TmpTreeComment,
                                               comment=comment,
                                               request=request)
            if comment.is_public:
                notify_comment_followers(new_comment)
    else:
        key = signed.dumps(comment, compress=True,
                           extra_key=settings.COMMENTS_TREE_SALT)
        site = get_current_site(request)
        send_email_confirmation_request(comment, key, site)


comment_was_posted.connect(on_comment_was_posted, sender=TmpTreeComment)


def sent(request, using=None):
    comment_pk = request.GET.get("c", None)
    try:
        comment_pk = int(comment_pk)
        comment = TreeComment.objects.get(pk=comment_pk)
    except (TypeError, ValueError, TreeComment.DoesNotExist):
        value = signing.loads(comment_pk)
        ctype, object_id = value.split(":")
        model = apps.get_model(*ctype.split(".", 1))
        target = model._default_manager.using(using).get(pk=object_id)
        template_arg = ["django_comments_tree/posted.html",
                        "comments/posted.html"]
        return render(request, template_arg, {'target': target})
    else:
        if request.is_ajax() and comment.user and comment.user.is_authenticated:
            if comment.is_public:
                template_arg = [
                    "django_comments_tree/%s/%s/comment.html" % (
                        comment.content_type.app_label,
                        comment.content_type.model),
                    "django_comments_tree/%s/comment.html" % (
                        comment.content_type.app_label,),
                    "django_comments_tree/comment.html"
                ]
            else:
                template_arg = get_moderated_tmpl(comment)
            return render(request, template_arg, {'comment': comment})
        else:
            if comment.is_public:
                return redirect(comment)
            else:
                moderated_tmpl = get_moderated_tmpl(comment)
                return render(request, moderated_tmpl, {'comment': comment})


def confirm(request, key,
            template_discarded="django_comments_tree/discarded.html"):
    try:
        tmp_comment = signed.loads(str(key),
                                   extra_key=settings.COMMENTS_TREE_SALT)
    except (ValueError, signed.BadSignature):
        raise Http404
    # the comment does exist if the URL was already confirmed, then: Http404
    if _comment_exists(tmp_comment):
        raise Http404
    # Send signal that the comment confirmation has been received
    responses = signals.confirmation_received.send(sender=TmpTreeComment,
                                                   comment=tmp_comment,
                                                   request=request)
    # Check whether a signal receiver decides to discard the comment
    for (receiver, response) in responses:
        if response is False:
            return render(request, template_discarded, {'comment': tmp_comment})

    comment = _create_comment(tmp_comment)
    if comment.is_public is False:
        return render(request, get_moderated_tmpl(comment),
                      {'comment': comment})
    else:
        notify_comment_followers(comment)
        return redirect(comment)


def notify_comment_followers(comment):
    """
    Updated to use MP_Nodes
    :param comment:
    :return:
    """
    root = comment.get_root()

    followers = {}
    kwargs = {'is_public': True,
              'followup': True}
    previous_comments = root.get_descendants()

    previous_comments = previous_comments.filter(**kwargs)
    previous_comments = previous_comments.exclude(user_email=comment.user_email)

    for instance in previous_comments:
        followers[instance.user_email] = (
            instance.user_name,
            signed.dumps(instance, compress=True,
                         extra_key=settings.COMMENTS_TREE_SALT))

    # model = apps.get_model(comment.content_type.app_label,
    #                        comment.content_type.model)
    # target = model._default_manager.get(pk=comment.object_id)
    subject = _("new comment posted")
    text_message_template = loader.get_template(
        "django_comments_tree/email_followup_comment.txt")
    if settings.COMMENTS_TREE_SEND_HTML_EMAIL:
        html_message_template = loader.get_template(
            "django_comments_tree/email_followup_comment.html")

    for email, (name, key) in six.iteritems(followers):
        mute_url = reverse('comments-tree-mute', args=[key.decode('utf-8')])
        message_context = {'user_name': name,
                           'comment': comment,
                           # 'content_object': target,
                           'mute_url': mute_url,
                           'site': comment.site}
        text_message = text_message_template.render(message_context)
        if settings.COMMENTS_TREE_SEND_HTML_EMAIL:
            html_message = html_message_template.render(message_context)
        else:
            html_message = None
        send_mail(subject, text_message, settings.COMMENTS_TREE_FROM_EMAIL,
                  [email, ], html=html_message)


def reply(request, cid):
    try:
        comment = TreeComment.objects.get(pk=cid)
        if not comment.allow_thread():
            raise MaxThreadLevelExceededException(comment)
    except MaxThreadLevelExceededException as exc:
        return HttpResponseForbidden(exc)
    except TreeComment.DoesNotExist as exc:
        raise Http404(exc)

    form = get_form()(comment.content_object, comment=comment)
    next = request.GET.get("next", reverse("comments-tree-sent"))

    template_arg = [
        "django_comments_tree/%s/%s/reply.html" % (
            comment.content_type.app_label,
            comment.content_type.model),
        "django_comments_tree/%s/reply.html" % (
            comment.content_type.app_label,),
        "django_comments_tree/reply.html"
    ]
    return render(request, template_arg,
                  {"comment": comment, "form": form, "cid": cid, "next": next})


def mute(request, key):
    try:
        comment = signed.loads(str(key),
                               extra_key=settings.COMMENTS_TREE_SALT)
    except (ValueError, signed.BadSignature):
        raise Http404
    # the comment does exist if the URL was already confirmed, then: Http404
    if not comment.followup or not _comment_exists(comment):
        raise Http404

    # Send signal that the comment thread has been muted
    signals.comment_thread_muted.send(sender=TreeComment,
                                      comment=comment,
                                      request=request)

    unmuted = comment.get_root().get_descendants().filter(
        is_public=True,
        followup=True,
        user_email=comment.user_email)
    unmuted.update(followup=False)

    model = apps.get_model(comment.content_type.app_label,
                           comment.content_type.model)
    target = model._default_manager.get(pk=comment.object_id)

    template_arg = [
        "django_comments_tree/%s/%s/muted.html" % (
            comment.content_type.app_label,
            comment.content_type.model),
        "django_comments_tree/%s/muted.html" % (
            comment.content_type.app_label,),
        "django_comments_tree/muted.html"
    ]
    return render(request, template_arg, {"content_object": target})


class CommentPostBadRequest(http.HttpResponseBadRequest):
    """
    Response returned when a comment post is invalid. If ``DEBUG`` is on a
    nice-ish error message will be displayed (for debugging purposes), but in
    production mode a simple opaque 400 page will be displayed.
    """

    def __init__(self, why):
        super(CommentPostBadRequest, self).__init__()
        if settings.DEBUG:
            self.content = render_to_string("comments/400-debug.html", {"why": why})


class CommentView(View):
    http_method_names = ['post']

    def post(self, request, next=None, using=None):
        """
        Post a comment.

        HTTP POST is required. If ``POST['submit'] == "preview"`` or if there are
        errors a preview template, ``comments/preview.html``, will be rendered.
        """
        # Fill out some initial data fields from an authenticated user, if present
        data = request.POST.copy()
        if request.user.is_authenticated:
            if not data.get('name', ''):
                data["name"] = request.user.get_full_name() or request.user.get_username()
            if not data.get('email', ''):
                data["email"] = request.user.email

        # Look up the object we're trying to comment about
        ctype = data.get("content_type")
        object_id = data.get("object_id")
        if ctype is None or object_id is None:
            return CommentPostBadRequest("Missing content_type or object_id field.")
        try:
            model = apps.get_model(*ctype.split(".", 1))
            target = model._default_manager.using(using).get(pk=object_id)
        except TypeError:
            return CommentPostBadRequest(
                "Invalid content_type value: %r" % escape(ctype))
        except AttributeError:
            return CommentPostBadRequest(
                "The given content-type %r does not resolve to a valid model." % escape(ctype))
        except ObjectDoesNotExist:
            return CommentPostBadRequest(
                "No object matching content-type %r and object PK %r exists." % (
                    escape(ctype), escape(object_id)))
        except (ValueError, ValidationError) as e:
            return CommentPostBadRequest(
                "Attempting go get content-type %r and object PK %r exists raised %s" % (
                    escape(ctype), escape(object_id), e.__class__.__name__))

        # Do we want to preview the comment?
        preview = "preview" in data

        # Construct the comment form
        form = get_form()(target, data=data)

        # Check security information
        if form.security_errors():
            return CommentPostBadRequest(
                f"The comment form failed security verification:"
                f" {escape(str(form.security_errors()))}")

        # If there are errors or if we requested a preview show the comment
        if form.errors or preview:
            app_lbl = model._meta.app_label
            nm = model._meta.model_name
            template_list = [
                # These first two exist for purely historical reasons.
                # Django v1.0 and v1.1 allowed the underscore format for
                # preview templates, so we have to preserve that format.
                f"comments/{app_lbl}_{nm}_preview.html",
                f"comments/{app_lbl}_preview.html",
                # Now the usual directory based template hierarchy.
                f"comments/{app_lbl}/{nm}/preview.html",
                f"comments/{app_lbl}/preview.html",
                "comments/preview.html",
            ]
            return render(request, template_list,
                          {
                              "comment": form.data.get("comment", ""),
                              "form": form,
                              "next": data.get("next", next),
                          },
                          )

        # Otherwise create the comment
        comment = form.get_comment_object(site_id=get_current_site(request).id)
        comment.ip_address = request.META.get("REMOTE_ADDR", None) or None
        if request.user.is_authenticated:
            comment.user = request.user

        # Signal that the comment is about to be saved
        responses = signals.comment_will_be_posted.send(
            sender=comment.__class__,
            comment=comment,
            request=request
        )

        for (receiver, response) in responses:
            if response is False:
                return CommentPostBadRequest(
                    "comment_will_be_posted receiver %r killed the comment" % receiver.__name__)

        # Save the comment and signal that it was saved
        comment.save()
        signals.comment_was_posted.send(
            sender=comment.__class__,
            comment=comment,
            request=request
        )

        return next_redirect(request, fallback=next or 'comments-comment-done',
                             c=comment._get_pk_val())


@csrf_protect
@require_POST
def post_comment(request, next=None, using=None):
    pass


comment_done = confirmation_view(
    template="comments/posted.html",
    doc="""Display a "comment was posted" success page."""
)


@method_decorator(login_required, name='dispatch')
class FlagView(View):
    http_method_names = ['get', 'post']

    def get_comment(self, comment_id):
        comment = get_object_or_404(get_comment_model(),
                                    pk=comment_id)
        if not has_app_model_option(comment)['allow_flagging']:
            ctype = ContentType.objects.get_for_model(comment.content_object)
            raise Http404("Comments posted to instances of '%s.%s' are not "
                          "explicitly allowed to receive 'removal suggestion' "
                          "flags. Check the COMMENTS_TREE_APP_MODEL_OPTIONS "
                          "setting." % (ctype.app_label, ctype.model))

        return comment

    def get(self, request, comment_id, next=None):
        comment = self.get_comment(comment_id)
        return render(request, 'comments/flag.html',
                      {'comment': comment,
                       'next': next})

    def post(self, request, comment_id, next=None):
        comment = self.get_comment(comment_id)

        perform_flag(request, comment)
        return next_redirect(request, fallback=next or 'comments-flag-done',
                             c=comment.pk)


@csrf_protect
@login_required
def like(request, comment_id, next=None):
    """
    Like a comment. Confirmation on GET, action on POST.

    Templates: :template:`django_comments_tree/like.html`,
    Context:
        comment
            the flagged `comments.comment` object
    """
    comment = get_object_or_404(get_comment_model(), pk=comment_id)
    if not has_app_model_option(comment)['allow_feedback']:
        ctype = ContentType.objects.get_for_model(comment.content_object)
        raise Http404("Comments posted to instances of '%s.%s' are not "
                      "explicitly allowed to receive 'liked it' flags. "
                      "Check the COMMENTS_TREE_APP_MODEL_OPTIONS "
                      "setting." % (ctype.app_label, ctype.model))
    # Flag on POST
    if request.method == 'POST':
        perform_like(request, comment)
        return next_redirect(request,
                             fallback=next or 'comments-tree-like-done',
                             c=comment.pk)
    # Render a form on GET
    else:
        liked_it = request.user in comment.users_flagging(LIKEDIT_FLAG)
        return render(request, 'django_comments_tree/like.html',
                      {'comment': comment,
                       'already_liked_it': liked_it,
                       'next': next})


@csrf_protect
@login_required
def dislike(request, comment_id, next=None):
    """
    Dislike a comment. Confirmation on GET, action on POST.

    Templates: :template:`django_comments_tree/dislike.html`,
    Context:
        comment
            the flagged `comments.comment` object
    """
    comment = get_object_or_404(get_comment_model(), pk=comment_id)

    if not has_app_model_option(comment)['allow_feedback']:
        ctype = ContentType.objects.get_for_model(comment.content_object)
        raise Http404("Comments posted to instances of '%s.%s' are not "
                      "explicitly allowed to receive 'disliked it' flags. "
                      "Check the COMMENTS_TREE_APP_MODEL_OPTIONS "
                      "setting." % (ctype.app_label, ctype.model))
    # Flag on POST
    if request.method == 'POST':
        perform_dislike(request, comment)
        return next_redirect(request,
                             fallback=(next or 'comments-tree-dislike-done'),
                             c=comment.pk)
    # Render a form on GET
    else:
        disliked_it = request.user in comment.users_flagging(DISLIKEDIT_FLAG)
        return render(request, 'django_comments_tree/dislike.html',
                      {'comment': comment,
                       'already_disliked_it': disliked_it,
                       'next': next})


def perform_like(request, comment):
    """Actually set the 'Likedit' flag on a comment from a request."""
    flag, created = TreeCommentFlag.objects.get_or_create(comment=comment,
                                                          user=request.user,
                                                          flag=LIKEDIT_FLAG)
    if created:
        TreeCommentFlag.objects.filter(comment=comment,
                                       user=request.user,
                                       flag=DISLIKEDIT_FLAG).delete()
    else:
        flag.delete()

    signals.comment_feedback_toggled.send(
        sender=flag.__class__,
        flag=flag,
        comment=comment,
        created=created,
        request=request,
    )
    return created


def perform_dislike(request, comment):
    """Actually set the 'Dislikedit' flag on a comment from a request."""
    flag, created = TreeCommentFlag.objects.get_or_create(comment=comment,
                                                          user=request.user,
                                                          flag=DISLIKEDIT_FLAG)
    if created:
        TreeCommentFlag.objects.filter(comment=comment,
                                       user=request.user,
                                       flag=LIKEDIT_FLAG).delete()
    else:
        flag.delete()

    signals.comment_feedback_toggled.send(
        sender=flag.__class__,
        flag=flag,
        comment=comment,
        created=created,
        request=request,
    )
    return created


like_done = confirmation_view(
    template="django_comments_tree/liked.html",
    doc='Displays a "I liked this comment" success page.'
)

dislike_done = confirmation_view(
    template="django_comments_tree/disliked.html",
    doc='Displays a "I disliked this comment" success page.'
)


class TreeCommentListView(ListView):
    page_range = 5
    content_types = None  # List of "app_name.model_name" strings.
    template_name = "django_comments_tree/comment_list.html"

    def get_content_types(self):
        if self.content_types is None:
            return None
        content_types = []
        for entry in self.content_types:
            app, model = entry.split('.')
            content_types.append(
                ContentType.objects.get(app_label=app, model=model)
            )
        return content_types

    def get_queryset(self):
        content_types = self.get_content_types()
        if content_types is None:
            return None
        # ToDo: This returns None or a qs
        return TreeComment.objects \
            .for_content_types(content_types,
                               site=settings.SITE_ID) \
            .filter(is_removed=False) \
            .order_by('submit_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'paginator' in context:
            index = context['page_obj'].number - 1
            prange = [n for n in context['paginator'].page_range]
            if len(prange) > self.page_range:
                if len(prange[index:]) >= self.page_range:
                    prange = prange[index:(index + self.page_range)]
                else:
                    prange = prange[-(self.page_range):]
            context['page_range'] = prange
        return context
