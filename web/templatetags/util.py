from crispy_forms.helper import FormHelper
from django import forms, template
from django.urls import reverse

from discussions import settings
from web import util

register = template.Library()


@register.filter(name="path_with_domain")
def path_with_domain(p):
    return util.path_with_domain(p)


@register.filter(name="discussions_url")
def discussions_url(q):
    return util.discussions_url(q, with_domain=False)


@register.filter(name="discussions_url_domain")
def discussions_url_domain(q):
    return util.discussions_url(q, with_domain=True)


@register.filter(name="short_url")
def short_url(d):
    path = reverse("web:short_url", args=[d.platform_id])
    return f"{settings.APP_SCHEME}://{settings.APP_DOMAIN}{path}"


@register.filter(name="story_short_url")
def story_short_url(d):
    path = reverse("web:story_short_url", args=[d.platform_id])
    return f"{settings.APP_SCHEME}://{settings.APP_DOMAIN}{path}"


@register.filter(name="url_root")
def url_root(u):
    return util.url_root(u)


@register.simple_tag(name="is_dev")
def is_dev():
    return util.is_dev()


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key, "")


@register.simple_tag
def htmx_attr(obj, name, value):
    if isinstance(obj, FormHelper):
        obj.attrs[name] = value
    elif isinstance(obj, forms.Field):
        # obj.update_attributes(**{name: value})
        obj.widget.attrs[name] = value
