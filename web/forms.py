# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
import logging
from collections.abc import Mapping, Sequence
from typing import ClassVar

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Button, Div, Field, Layout, Submit
from django import forms
from django.urls import reverse
from typing_extensions import override

from web.platform import Platform

from . import models

logger = logging.getLogger(__name__)


class HtmxFormHelper(FormHelper):
    def set_attr(self, name: str, value: str) -> None:
        self.attrs[name] = value


class QueryForm(forms.Form):
    query = forms.CharField()
    platforms = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple(attrs={"checked": ""}),
        choices=Platform.choices,
    )

    tags = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple(attrs={"checked": ""}),
    )


class SubscriberForm(forms.ModelForm):
    class Meta(
        forms.models.ModelFormOptions,
    ):
        model = models.Subscriber
        fields = ["topic", "email"]  # noqa: RUF012

    contact_email_only: forms.BooleanField = forms.BooleanField(
        required=False,
        label="By email *",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["topic"].choices = [
            (k, v) for (k, v) in self.fields["topic"].choices if k != "laarc"
        ]

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

    @override
    def save(self, commit=True):  # noqa: FBT002
        instance = super().save(commit=False)
        if self.cleaned_data.get("contact_email_only"):
            instance.suspected_spam = True
        if commit:
            instance.save()
        return instance


class UnsubscribeForm(forms.ModelForm):
    class Meta(
        forms.models.ModelFormOptions,
    ):
        model = models.Subscriber
        fields = [  # noqa: RUF012
            "topic",
            "email",
            "verification_code",
            "unsubscribed_feedback",
        ]
        widgets = {  # noqa: RUF012
            "verification_code": forms.HiddenInput(),
            "unsubscribed_feedback": forms.Textarea(attrs={"rows": 4}),
        }


class ProfileForm(forms.ModelForm):
    class Meta(
        forms.models.ModelFormOptions,
    ):
        model = models.CustomUser
        fields = [  # noqa: RUF012
            "complete_name",
        ]  # , "generic_ads", "job_ads"]
        widgets = {"complete_name": forms.TextInput()}  # noqa: RUF012


class ADForm(forms.ModelForm):
    class Meta(
        forms.models.ModelFormOptions,
    ):
        model = models.AD

        fields: Sequence[str] = [
            "topics",
            "newsletter",
            "twitter",
            "mastodon",
            "body",
            "floss_repository",
            "consecutive_weeks",
            "comments",
        ]

        widgets: Mapping[str, forms.Widget] = {
            "floss_repository": forms.TextInput(),
            "title": forms.TextInput(),
            "body": forms.Textarea(attrs={"rows": 4}),
            "comments": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["consecutive_weeks"].initial = 1
        self.fields["body"].required = False
        # TODO: specify min_value in model?
        self.fields["consecutive_weeks"].min_value = 1
        self.fields["consecutive_weeks"].max_value = 4
        # self.fields["topics"].choices = weekly.topics_open_rate()

        self.helper = FormHelper(self)
        self.helper.form_method = "post"
        self.helper.attrs = {
            "hx-post": reverse("web:new_ad"),
            #     "hx-trigger": "input from: find ",
        }

        # _ = self.helper["topics"].wrap(
        #     Field,
        #     css_class="overflow-y-scroll h-max-10em ms-2",
        # )

        # Note: the actual submit button is added inside views.py

        self.helper.add_input(
            Submit(
                "simulate-new-ad",
                "Simulate price",
                css_class="btn btn-secondary",
            ),
        )


class MentionForm(forms.ModelForm):
    # TODO: fix like adform topics
    exclude_platforms = forms.MultipleChoiceField(
        help_text=models.Mention._meta.get_field(  # noqa: SLF001
            "exclude_platforms",
        ).help_text,
        widget=forms.CheckboxSelectMultiple(),
    )

    class Meta(
        forms.models.ModelFormOptions,
    ):
        model = models.Mention
        fields = (
            "base_url",
            "keywords",
            "exclude_platforms",
            "subreddits_exclude",
            "min_comments",
            "min_score",
            "rule_name",
        )

        widgets: ClassVar[dict[str, forms.widgets.Input]] = {
            "base_url": forms.TextInput(),
            "keyword": forms.TextInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["exclude_platforms"].choices = Platform.choices
        self.fields["exclude_platforms"].required = False
        self.fields["min_comments"].required = False
        self.fields["min_score"].required = False

        self.helper = FormHelper(self)
        _ = self.helper["exclude_platforms"].wrap(
            Field,
            css_class="overflow-y-scroll h-max-10em ms-2",
        )

        # for field_name, field in self.fields.items():

        self.helper.form_method = "post"
        self.helper.add_input(
            Submit(
                "submit-new-mention-rule",
                "Create rule",
                css_class="btn btn-secondary",
            ),
        )
        self.helper.add_input(
            Button(
                "live-preview-mention-rule",
                "Live preview",
                css_class="btn btn-info",
            ),
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
        for subreddit in data:
            sub = subreddit.removeprefix("/r/")
            sub = sub.removeprefix("r/")
            sub = sub.strip().lower()
            new_list.append(sub)

        return new_list

    @override
    def clean(self):
        cleaned_data = super().clean()
        base_url = cleaned_data.get("base_url")
        keywords = cleaned_data.get("keywords")

        if not base_url and not keywords:
            msg = "Please fill at least one of URL prefix or keywords."
            self.add_error("base_url", msg)
            self.add_error("keywords", msg)


class EditMentionForm(MentionForm):
    class Meta(MentionForm.Meta):
        fields = (*MentionForm.Meta.fields, "disabled")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper.inputs = []

        self.helper.add_input(
            Submit(
                "submit-edit-mention-rule",
                "Update rule",
                css_class="btn btn-secondary",
            ),
        )

        self.helper.add_input(
            Button(
                "live-preview-mention-rule",
                "Live preview",
                css_class="btn btn-info",
            ),
        )
