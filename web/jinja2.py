# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
from django.templatetags.static import static
from django.urls import reverse
from jinja2 import Environment

from web import util


def pluralize(number, singular="", plural="s"):
    if number == 1:
        return singular
    else:
        return plural


def environment(**options):
    env = Environment(**options)
    env.globals.update(
        {
            "static": static,
            "url": reverse,
            "pluralize": pluralize,
            "util": util,
        },
    )
    return env
