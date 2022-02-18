from web import util
from django import template

register = template.Library()


@register.filter(name="discussions_url")
def discussions_url(q):
    return util.discussions_url(q, with_domain=False)


@register.filter(name="discussions_url_domain")
def discussions_url_domain(q):
    return util.discussions_url(q, with_domain=True)
