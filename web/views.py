from django.http import HttpResponse


def index(request):
    html = '<html><body>Test GitHub deploy</body></html>'

    return HttpResponse(html)
