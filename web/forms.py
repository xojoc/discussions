import logging

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Field, Submit, Layout, Div
from django import forms

# from crispy_bootstrap5.bootstrap5 import FloatingField

from . import models, topics

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
        fields = ["topic", "email", "verification_code"]
        widgets = {"verification_code": forms.HiddenInput()}


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
            "keyword",
            "exclude_platforms",
            # "subreddits_only",
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

        if data and not data.endswith("/"):
            data += "/"

        return data

    def clean(self):
        cleaned_data = super(MentionForm, self).clean()
        base_url = cleaned_data.get("base_url")
        keyword = cleaned_data.get("keyword")
        subreddits_only = cleaned_data.get("subreddits_only")
        subreddits_exclude = cleaned_data.get("subreddits_exclude")

        if not base_url and not keyword:
            msg = "Please fill at least one of URL prefix or Keyword."
            self.add_error("base_url", msg)
            self.add_error("keyword", msg)

        if subreddits_only and subreddits_exclude:
            msg = "Please fill only one of Subreddits whitelist or Subreddits blacklist."
            self.add_error("subreddits_only", msg)
            self.add_error("subreddits_exclude", msg)


class EditMentionForm(MentionForm):
    def __init__(self, *args, **kwargs):
        super(EditMentionForm, self).__init__(*args, **kwargs)

        self.helper.inputs.pop()
        self.helper.add_input(
            Submit(
                "submit-edit-mention-rule",
                "Update rule",
                css_class="btn btn-secondary",
            )
        )
