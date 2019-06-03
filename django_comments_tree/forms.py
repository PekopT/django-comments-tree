from django import forms
from django.apps import apps
from django.utils.translation import ugettext_lazy as _

from django_comments.forms import CommentForm

from django_comments_tree.conf import settings
from django_comments_tree.models import TmpTreeComment


class TreeCommentForm(CommentForm):
    followup = forms.BooleanField(required=False,
                                  label=_("Notify me about follow-up comments"))
    reply_to = forms.IntegerField(required=True, initial=0,
                                  widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        comment = kwargs.pop("comment", None)
        if comment:
            initial = kwargs.pop("initial", {})
            initial.update({"reply_to": comment.pk})
            kwargs["initial"] = initial
            followup_suffix = ('_%d' % comment.pk)
        else:
            followup_suffix = ''
        super().__init__(*args, **kwargs)
        self.fields['name'] = forms.CharField(
            label=_("Name"),
            widget=forms.TextInput(attrs={'placeholder': _('name'),
                                          'class': 'form-control'}))
        self.fields['email'] = forms.EmailField(
            label=_("Mail"), help_text=_("Required for comment verification"),
            widget=forms.TextInput(attrs={'placeholder': _('mail address'),
                                          'class': 'form-control'}))
        self.fields['url'] = forms.URLField(
            label=_("Link"), required=False,
            widget=forms.TextInput(attrs={
                'placeholder': _('url your name links to (optional)'),
                'class': 'form-control'}))
        self.fields['comment'] = forms.CharField(
            widget=forms.Textarea(attrs={'placeholder': _('Your comment'),
                                         'class': 'form-control'}),
            max_length=settings.COMMENT_MAX_LENGTH)
        self.fields['comment'].widget.attrs.pop('cols')
        self.fields['comment'].widget.attrs.pop('rows')
        self.fields['followup'].widget.attrs['id'] = (
            'id_followup%s' % followup_suffix)
        self.fields['followup'].widget.attrs['class'] = "custom-control-input"

    def get_comment_model(self):
        return TmpTreeComment

    def get_comment_create_data(self, site_id=None):
        data = super().get_comment_create_data(site_id=site_id)
        ctype = data.get('content_type')
        object_pk = data.get('object_pk')
        model = apps.get_model(ctype.app_label, ctype.model)
        target = model._default_manager.get(pk=object_pk)
        data.update({'followup': self.cleaned_data['followup'],
                     'content_object': target})
        return data
