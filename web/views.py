from django.shortcuts import render
import datetime
from django.http import HttpResponse
from . import models
from django.utils.timezone import make_aware

def index(request):
    now = datetime.datetime.now()
    html = '<html><body>It is now %s.</body></html>' % now

    return HttpResponse(html)