from django import forms
from . import models
import secrets

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
