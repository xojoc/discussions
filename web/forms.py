from django import forms
from . import models

PLATFORM_CHOICES = [("h", "Hacker News"), ("l", "Lobsters")]


class QueryForm(forms.Form):
    query = forms.CharField()
    platforms = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple(attrs={"checked": ""}),
        choices=PLATFORM_CHOICES,
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
        fields = ["complete_name", "generic_ads", "job_ads"]
        widgets = {"complete_name": forms.TextInput()}
        # labels = {"email": "Primary email"}
        # help_texts = {
        #     "email": "See below on how to manage your emails",
        # }
        # readonly = ("email",)
