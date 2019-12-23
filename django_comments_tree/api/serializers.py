import hashlib

try:
    from urllib.parse import urlencode
except ImportError:
    from urllib import urlencode

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.shortcuts import get_current_site
from django.utils import formats
from django.utils.html import escape
from django.utils.translation import ugettext as _, activate, get_language

from django_comments_tree import get_form
from django_comments_tree.models import TreeCommentFlag
from django_comments_tree.signals import comment_will_be_posted, comment_was_posted
from rest_framework import serializers

from django_comments_tree import signed
from django_comments_tree.views import comments as views
from django_comments_tree.conf import settings
from django_comments_tree.models import (TmpTreeComment, TreeComment,
                                         LIKEDIT_FLAG, DISLIKEDIT_FLAG)
from django_comments_tree.signals import confirmation_received
from django_comments_tree.utils import has_app_model_option

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
COMMENT_MAX_LENGTH = getattr(settings, 'COMMENT_MAX_LENGTH', 3000)


class SerializerSaveMixin:

    def on_save(self, **kwargs):
        resp = {
            'code': 200,
            'comment': self.instance,
        }
        # Signal that the comment is about to be saved
        responses = comment_will_be_posted.send(sender=self.instance.__class__,
                                                comment=self.instance,
                                                request=self.request)
        for (receiver, response) in responses:
            if response is False:
                resp['code'] = 403  # Rejected.
                return resp

        return resp


class APICommentSerializer(SerializerSaveMixin, serializers.ModelSerializer):
    class Meta:
        model = TreeComment
        fields = ['id', 'user',
                  'user_name', 'user_email', 'user_url',
                  'comment', 'comment_markup_type',
                  'submit_date', 'updated_on',
                  'ip_address', 'is_public', 'is_removed',
                  'followup',
                  ]

    def __init__(self, *args, **kwargs):
        if kwargs.get('context'):
            self.request = kwargs.get('context').get('request')
        super().__init__(*args, **kwargs)

    def to_representation(self, instance):
        obj = super().to_representation(instance)
        obj['submit_date'] = instance.submit_date.strftime(DATETIME_FORMAT)
        return obj

    def create(self, validated_data):
        if 'parent' in validated_data:
            p = validated_data.pop('parent')
            instance = p.add_child(**validated_data)
            return instance

        return super().create(validated_data)

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)

    def save(self, **kwargs):
        created = kwargs.pop('create', False)
        result = super().save(**kwargs)

        # Call after save, or instance won't be set
        response = self.on_save(**kwargs)
        if response.get('code') != 200:
            return response.get('code')

        comment_was_posted.send(sender=self.instance.__class__,
                                comment=self.instance,
                                request=self.request,
                                created=created)

        return result


class WriteCommentSerializer(serializers.Serializer):
    content_type = serializers.CharField()
    object_id = serializers.CharField()
    timestamp = serializers.CharField()
    security_hash = serializers.CharField()
    honeypot = serializers.CharField(allow_blank=True)
    name = serializers.CharField(allow_blank=True)
    email = serializers.EmailField(allow_blank=True)
    url = serializers.URLField(required=False)
    comment = serializers.CharField(max_length=COMMENT_MAX_LENGTH)
    followup = serializers.BooleanField(default=False)
    reply_to = serializers.IntegerField(default=0)

    def __init__(self, *args, **kwargs):
        self.request = kwargs['context']['request']
        self.form = None
        super().__init__(*args, **kwargs)

    def validate_name(self, value):
        if not len(value):
            fnl = len(self.request.user.get_full_name())
            if not fnl or not self.request.user.is_authenticated:
                raise serializers.ValidationError("This field is required")
            else:
                return self.request.user.get_full_name() or self.request.user.get_username()
        return value

    def validate_email(self, value):
        if not len(value):
            eml = len(self.request.user.email)
            if not eml or not self.request.user.is_authenticated:
                raise serializers.ValidationError("This field is required")
            else:
                return self.request.user.email
        return value

    def validate(self, data):
        ctype = data.get("content_type")
        object_id = data.get("object_id")
        if ctype is None or object_id is None:
            return serializers.ValidationError("Missing content_type or "
                                               "object_id field.")
        try:
            model = apps.get_model(*ctype.split(".", 1))
            target = model._default_manager.get(pk=object_id)
        except TypeError:
            return serializers.ValidationError("Invalid content_type value: %r"
                                               % escape(ctype))
        except AttributeError:
            return serializers.ValidationError("The given content-type %r does "
                                               "not resolve to a valid model."
                                               % escape(ctype))
        except model.ObjectDoesNotExist:
            return serializers.ValidationError(
                "No object matching content-type %r and object ID %r exists."
                % (escape(ctype), escape(object_id)))
        except (ValueError, serializers.ValidationError) as e:
            return serializers.ValidationError(
                "Attempting go get content-type %r and object ID %r exists "
                "raised %s" % (escape(ctype), escape(object_id),
                               e.__class__.__name__))

        self.form = get_form()(target, data=data)

        # Check security information
        if self.form.security_errors():
            return serializers.ValidationError(
                "The comment form failed security verification: %s" %
                escape(str(self.form.security_errors())))
        if self.form.errors:
            return serializers.ValidationError(self.form.errors)
        return data

    def save(self):
        # resp object is a dictionary. The code key indicates the possible
        # four states the comment can be in:
        #  * Comment created (http 201),
        #  * Confirmation sent by mail (http 204),
        #  * Comment in moderation (http 202),
        #  * Comment rejected (http 403).
        site = get_current_site(self.request)

        try:
            comment_object = self.form.get_comment_object(site_id=site.id)
        except ValueError:
            raise serializers.ValidationError(self.form.errors)

        resp = {
            'code': -1,
            'comment': comment_object
        }

        resp['comment'].ip_address = self.request.META.get("REMOTE_ADDR", None)

        if self.request.user.is_authenticated:
            resp['comment'].user = self.request.user

        # Signal that the comment is about to be saved
        responses = comment_will_be_posted.send(sender=TmpTreeComment,
                                                comment=resp['comment'],
                                                request=self.request)
        for (receiver, response) in responses:
            if response is False:
                resp['code'] = 403  # Rejected.
                return resp

        # Replicate logic from django_comments_tree.views.comments.on_comment_was_posted.
        if not settings.COMMENTS_TREE_CONFIRM_EMAIL or self.request.user.is_authenticated:
            if not views._comment_exists(resp['comment']):
                new_comment = views._create_comment(resp['comment'])
                resp['comment'].tree_comment = new_comment
                confirmation_received.send(sender=TmpTreeComment,
                                           comment=resp['comment'],
                                           request=self.request)
                comment_was_posted.send(sender=new_comment.__class__,
                                        comment=new_comment,
                                        request=self.request)
                if resp['comment'].is_public:
                    resp['code'] = 201
                    views.notify_comment_followers(new_comment)
                else:
                    resp['code'] = 202
        else:
            key = signed.dumps(resp['comment'], compress=True,
                               extra_key=settings.COMMENTS_TREE_SALT)
            views.send_email_confirmation_request(resp['comment'], key, site)
            resp['code'] = 204  # Confirmation sent by mail.

        return resp


class ReadCommentSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    user_url = serializers.SerializerMethodField()
    user_moderator = serializers.SerializerMethodField()
    user_avatar = serializers.SerializerMethodField()
    submit_date = serializers.SerializerMethodField()
    parent_id = serializers.SerializerMethodField(read_only=True)
    level = serializers.IntegerField(read_only=True, source='thread_level')
    is_removed = serializers.BooleanField(read_only=True)
    comment = serializers.SerializerMethodField()
    allow_reply = serializers.SerializerMethodField()
    permalink = serializers.SerializerMethodField()
    flags = serializers.SerializerMethodField()

    class Meta:
        model = TreeComment
        fields = ('id', 'user_name', 'user_url', 'user_moderator',
                  'user_avatar', 'permalink', 'comment', 'submit_date',
                  'parent_id', 'level', 'is_removed', 'allow_reply', 'flags')

    def __init__(self, *args, **kwargs):
        self.request = kwargs['context']['request']
        super().__init__(*args, **kwargs)

    def get_parent_id(self, obj):
        return obj.get_parent().pk if obj.get_parent().depth > 1 else None

    def get_user_name(self, obj):
        if obj.user_name:
            return obj.user_name
        elif obj.user:
            return settings.COMMENTS_TREE_API_USER_REPR(obj.user)
        else:
            return None

    def get_user_url(self, obj):
        if obj.user_url:
            return obj.user_url
        elif obj.user:
            return settings.COMMENTS_TREE_API_USER_URL_REPR(obj.user)
        else:
            return None

    def get_submit_date(self, obj):
        activate(get_language())
        return formats.date_format(obj.submit_date, 'DATETIME_FORMAT',
                                   use_l10n=True)

    def get_comment(self, obj):
        if obj.is_removed:
            return _("This comment has been removed.")
        else:
            return str(obj.comment)

    def get_user_moderator(self, obj):
        try:
            if obj.user and obj.user.has_perm('comments.can_moderate'):
                return True
            else:
                return False
        except Exception:
            return None

    def get_flags(self, obj):
        flags = {
            'like': {'active': False, 'count': 0},
            'dislike': {'active': False, 'count': 0},
        }
        users_likedit, users_dislikedit = None, None

        if has_app_model_option(obj)['allow_flagging']:
            flags['removal'] = {'active': False, 'count': None}

            users_flagging = obj.users_flagging(TreeCommentFlag.SUGGEST_REMOVAL)
            if self.request.user in users_flagging:
                flags['removal']['active'] = True
            if self.request.user.has_perm("django_comments.can_moderate"):
                flags['removal']['count'] = len(users_flagging)

        opt = has_app_model_option(obj)
        if opt['allow_feedback'] or opt['show_feedback']:
            users_likedit = obj.users_flagging(LIKEDIT_FLAG)
            if users_likedit:
                flags['like']['count'] = len(users_likedit)

            users_dislikedit = obj.users_flagging(DISLIKEDIT_FLAG)

            if users_dislikedit:
                flags['dislike']['count'] = len(users_dislikedit)

        if has_app_model_option(obj)['allow_feedback']:
            if self.request.user in users_likedit:
                flags['like']['active'] = True

            elif self.request.user in users_dislikedit:
                flags['dislike']['active'] = True

        if has_app_model_option(obj)['show_feedback']:
            flags['like']['users'] = [
                "%d:%s" % (user.id, settings.COMMENTS_TREE_API_USER_REPR(user))
                for user in users_likedit]
            flags['dislike']['users'] = [
                "%d:%s" % (user.id, settings.COMMENTS_TREE_API_USER_REPR(user))
                for user in users_dislikedit]
        return flags

    def get_allow_reply(self, obj):
        return obj.allow_thread()

    def get_user_avatar(self, obj):
        if settings.COMMENTS_TREE_API_USER_AVATAR_FIELD and obj.user:
            avatar = getattr(obj.user, settings.COMMENTS_TREE_API_USER_AVATAR_FIELD)
            if avatar:
                return avatar.url
            else:
                return None

        path = hashlib.md5(obj.user_email.lower().encode('utf-8')).hexdigest()
        param = urlencode({'s': 48})
        return "https://www.gravatar.com/avatar/%s?%s&d=mm" % (path, param)

    def get_permalink(self, obj):
        return obj.get_absolute_url()


class FlagSerializer(serializers.ModelSerializer):
    flag_choices = {'like': LIKEDIT_FLAG,
                    'dislike': DISLIKEDIT_FLAG,
                    'report': TreeCommentFlag.SUGGEST_REMOVAL}

    class Meta:
        model = TreeCommentFlag
        fields = ('comment', 'flag',)

    def validate(self, data):
        # Validate flag.
        if data['flag'] not in self.flag_choices:
            raise serializers.ValidationError("Invalid flag.")
        # Check commenting options on object being commented.
        option = ''
        if data['flag'] in ['like', 'dislike']:
            option = 'allow_feedback'
        elif data['flag'] == 'report':
            option = 'allow_flagging'
        comment = data['comment']
        if not has_app_model_option(comment)[option]:
            ctype = ContentType.objects.get_for_model(comment.content_object)
            raise serializers.ValidationError(
                "Comments posted to instances of '%s.%s' are not explicitly "
                "allowed to receive '%s' flags. Check the "
                "COMMENTS_TREE_APP_MODEL_OPTIONS setting." % (
                    ctype.app_label, ctype.model, data['flag']
                )
            )
        data['flag'] = self.flag_choices[data['flag']]
        return data
