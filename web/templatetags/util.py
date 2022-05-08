from discussions import settings
from django import template
from django.urls import reverse
from web import util

register = template.Library()


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
