from django import forms

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
