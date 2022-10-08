from django import forms
from . import models, topics
from crispy_forms.layout import Field, Submit
from crispy_forms.helper import FormHelper


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
    class Meta:
        model = models.Subscriber
        fields = ["topic", "email"]


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


class MentionForm(forms.ModelForm):
    platforms = forms.MultipleChoiceField(
        choices=models.PLATFORM_CHOICES,
        help_text=models.Mention._meta.get_field("platforms").help_text,
        widget=forms.CheckboxSelectMultiple(),
    )

    class Meta:
        model = models.Mention
        fields = [
            # "rule_name",
            "base_url",
            "keyword",
            # "title_pattern",
            "platforms",
            "subreddits_only",
            "subreddits_exclude",
            "min_comments",
            "min_score",
            # "disabled",
        ]

        widgets = {
            "base_url": forms.TextInput(),
            "keyword": forms.TextInput(),
            # "url_pattern": forms.TextInput(),
            # "title_pattern": forms.TextInput(),
        }

    def __init__(self, *args, **kwargs):
        super(MentionForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper["platforms"].wrap(
            Field, css_class="overflow-y-scroll h-max-10em ms-2"
        )
        self.helper.form_method = "post"
        self.helper.add_input(
            Submit(
                "submit-new-mention-rule",
                "Submit Mention",
                css_class="btn btn-secondary",
            )
        )
