def is_form_spammer(request, form):
    spammer_ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.5359.124 Safari/537.36"
    spammer_ua = " ".join(spammer_ua.lower().split(" "))
    ua = request.headers.get("User-Agent", "")
    ua = " ".join(ua.lower().split(" "))
    if (
        form.cleaned_data.get("contact_email_only")
        and request.path_info == "/weekly/zig/"
        and ua == spammer_ua
        and request.headers.get("Connection") == "close"
    ):
        return 1
    return 0
