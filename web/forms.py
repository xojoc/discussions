import logging

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Field, Submit, Layout, Div, Button
from django import forms

from web import weekly, topics

# from crispy_bootstrap5.bootstrap5 import FloatingField

from . import models

logger = logging.getLogger(__name__)


class QueryForm(forms.Form):
    query = forms.CharField()
    platforms = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple(attrs={"checked": ""}),
        choices=models.PLATFORM_CHOICES,
    )

    tags = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple(attrs={"checked": ""})
    )


class SubscriberForm(forms.ModelForm):
    contact_email_only = forms.BooleanField(required=False, label="By email *")

    class Meta:
        model = models.Subscriber
        fields = ["topic", "email"]

    def __init__(self, *args, **kwargs):
        super(SubscriberForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_method = "POST"
        self.helper.layout = Layout(
            Field("topic"),
            Field("email"),
            Div(
                Field(
                    "contact_email_only",
                    autocomplete="off",
                    tabindex="-1",
                ),
                css_class="d-none",
            ),
            Submit("submit", "Subscribe for Free!"),
        )

    def save(self, commit=True):
        instance = super(SubscriberForm, self).save(commit=False)
        if self.cleaned_data.get("contact_email_only"):
            instance.suspected_spam = True
        if commit:
            instance.save()
        return instance


class UnsubscribeForm(forms.ModelForm):
    class Meta:
        model = models.Subscriber
        fields = [
            "topic",
            "email",
            "verification_code",
            "unsubscribed_feedback",
        ]
        widgets = {
            "verification_code": forms.HiddenInput(),
            "unsubscribed_feedback": forms.Textarea(attrs={"rows": 4}),
        }


class ProfileForm(forms.ModelForm):
    class Meta:
        model = models.CustomUser
        fields = ["complete_name"]  # , "generic_ads", "job_ads"]
        widgets = {"complete_name": forms.TextInput()}
        # labels = {"email": "Primary email"}
        # help_texts = {
        #     "email": "See below on how to manage your emails",
        # }
        # readonly = ("email",)


class SimulateADForm(forms.ModelForm):
    topics = forms.MultipleChoiceField(
        choices=topics.topics_choices,
        help_text=models.AD._meta.get_field("topics").help_text,
        widget=forms.CheckboxSelectMultiple(),
    )

    class Meta:
        model = models.AD
        fields = [
            "topics",
            "newsletter",
            "twitter",
            "mastodon",
            "floss_project",
            "consecutive_weeks",
        ]

    def __init__(self, *args, **kwargs):
        super(SimulateADForm, self).__init__(*args, **kwargs)
        self.fields["consecutive_weeks"].initial = 1
        self.fields["consecutive_weeks"].min_value = 1
        self.fields["consecutive_weeks"].max_value = 4
        self.fields["topics"].choices = weekly.topics_open_rate()

        self.helper = FormHelper(self)
        self.helper["topics"].wrap(
            Field, css_class="overflow-y-scroll h-max-10em ms-2"
        )
        self.helper.form_method = "post"
        self.helper.add_input(
            Submit(
                "simulate-new-ad",
                "Simulate price",
                css_class="btn btn-secondary",
            )
        )


class ADForm(forms.ModelForm):
    topics = forms.MultipleChoiceField(
        # choices=topics.topics_choices,
        choices=weekly.topics_open_rate(),
        help_text=models.AD._meta.get_field("topics").help_text,
        widget=forms.CheckboxSelectMultiple(),
    )

    class Meta:
        model = models.AD
        fields = [
            "topics",
            "newsletter",
            "twitter",
            "mastodon",
            "body",
            "floss_repository",
            "consecutive_weeks",
            "comments",
        ]

        widgets = {
            "floss_repository": forms.TextInput(),
            "title": forms.TextInput(),
            "body": forms.Textarea(attrs={"rows": 4}),
            "comments": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super(ADForm, self).__init__(*args, **kwargs)
        self.fields["consecutive_weeks"].initial = 1
        self.fields["consecutive_weeks"].min_value = 1
        self.fields["consecutive_weeks"].max_value = 4
        self.fields["topics"].choices = weekly.topics_open_rate()

        self.helper = FormHelper(self)
        self.helper["topics"].wrap(
            Field, css_class="overflow-y-scroll h-max-10em ms-2"
        )
        self.helper.form_method = "post"
        self.helper.add_input(
            Submit(
                "submit-new-ad",
                "Submit ad",
                css_class="btn btn-primary",
            )
        )


def _platform_choices():
    return [(k, v[0]) for k, v in models.Discussion.platforms().items()]


class MentionForm(forms.ModelForm):
    exclude_platforms = forms.MultipleChoiceField(
        help_text=models.Mention._meta.get_field(
            "exclude_platforms"
        ).help_text,
        widget=forms.CheckboxSelectMultiple(),
    )

    class Meta:
        model = models.Mention
        fields = [
            "base_url",
            "keywords",
            "exclude_platforms",
            "subreddits_exclude",
            "min_comments",
            "min_score",
            "rule_name",
        ]

        widgets = {
            "base_url": forms.TextInput(),
            "keyword": forms.TextInput(),
        }

    def __init__(self, *args, **kwargs):
        super(MentionForm, self).__init__(*args, **kwargs)
        self.fields["exclude_platforms"].choices = _platform_choices()
        self.fields["exclude_platforms"].required = False
        self.fields["min_comments"].required = False
        self.fields["min_score"].required = False

        self.helper = FormHelper(self)
        self.helper["exclude_platforms"].wrap(
            Field, css_class="overflow-y-scroll h-max-10em ms-2"
        )

        # self.helper.layout = Layout()
        # for field_name, field in self.fields.items():
        #     self.helper.layout.append(FloatingField(field_name))
        # self.helper.form_show_labels = False

        self.helper.form_method = "post"
        self.helper.add_input(
            Submit(
                "submit-new-mention-rule",
                "Create rule",
                css_class="btn btn-secondary",
            )
        )
        self.helper.add_input(
            Button(
                "live-preview-mention-rule",
                "Live preview",
                css_class="btn btn-info",
            )
        )

    def clean_min_comments(self):
        data = self.cleaned_data["min_comments"]
        if not data:
            return 0
        return data

    def clean_min_score(self):
        data = self.cleaned_data["min_score"]
        if not data:
            return 0
        return data

    def clean_base_url(self):
        data = self.cleaned_data["base_url"] or ""
        prev_data = data
        while True:
            data = data.strip()
            data = data.removeprefix("http://")
            data = data.removeprefix("https://")
            data = data.removeprefix("/")
            if data == prev_data:
                break
            prev_data = data

        if data:
            if "." not in data:
                msg = "Must contain at least one dot (.)"
                self.add_error("base_url", msg)

            min_len = 3
            if len(data) < min_len:
                msg = f"Must be at least {min_len} characters long"
                self.add_error("base_url", msg)

        return data

    def clean_keywords(self):
        data = self.cleaned_data["keywords"] or []

        max_len = 3
        if len(data) > max_len:
            msg = f"No more than {max_len} keywords are allowed"
            self.add_error("keywords", msg)

        for key in data:
            if not key.strip():
                msg = "Empty keywords are not allowed"
                self.add_error("keywords", msg)
                break

        return data

    def clean_subreddits_exclude(self):
        data = self.cleaned_data.get("subreddits_exclude") or []
        new_list = []
        for sub in data:
            sub = sub.removeprefix("/r/")
            sub = sub.removeprefix("r/")
            sub = sub.strip().lower()
            new_list.append(sub)

        return new_list

    def clean(self):
        cleaned_data = super(MentionForm, self).clean()
        base_url = cleaned_data.get("base_url")
        keywords = cleaned_data.get("keywords")

        if not base_url and not keywords:
            msg = "Please fill at least one of URL prefix or keywords."
            self.add_error("base_url", msg)
            self.add_error("keywords", msg)


class EditMentionForm(MentionForm):
    class Meta(MentionForm.Meta):
        fields = MentionForm.Meta.fields + ["disabled"]

    def __init__(self, *args, **kwargs):
        super(EditMentionForm, self).__init__(*args, **kwargs)

        self.helper.inputs = []

        self.helper.add_input(
            Submit(
                "submit-edit-mention-rule",
                "Update rule",
                css_class="btn btn-secondary",
            )
        )

        self.helper.add_input(
            Button(
                "live-preview-mention-rule",
                "Live preview",
                css_class="btn btn-info",
            )
        )
