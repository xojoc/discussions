# Copyright 2021 Alexandru Cojocaru AGPLv3 or later - no warranty!
import re
import unicodedata

from web.platform import Platform

from . import util


def __lobsters(title):
    return title
    title = title.removeprefix("show lobsters ")
    title = title.removeprefix("show lobste.rs ")
    title = title.removeprefix("show lobste rs ")
    return None


def __reddit(title):
    return title


def __hacker_news(title):
    return title
    title = title.removeprefix("show hn ")
    title = title.removeprefix("ask hn ")
    title = title.removeprefix("tell hn ")
    title = title.strip()
    return None


def __lambda_the_ultimate(title):
    return title


def __unicode(title):
    title = unicodedata.normalize("NFKC", title)
    table = str.maketrans({"`": "'", "“": '"', "”": '"', "-": "-"})
    return title.translate(table)


def __year(title):
    if re.search(r"\(1|2\d\d\d\)$", title):
        title = title[: -len("(1234)")]
    return title.strip()


def __format(title):
    title = title.removesuffix("[pdf]")
    title = title.removesuffix("[video]")
    return title.strip()


def __punctuation(title):
    title = title.replace("'s ", " ")
    new_title = ""
    for w in title.split():
        w2 = util.strip_punctuation(w)

        new_title += w2
        new_title += " "

    return " ".join(new_title.split())


def __contraction(title):
    new_title = ""
    for w in title.split():
        if w == "isn't":
            new_title += "is not"
        elif w == "won't":
            new_title += "will not"
        elif w in ("can't", "cannot"):
            new_title += "can not"
        elif w.endswith("'re"):
            new_title += w.removesuffix("'re") + " are"
        elif w.endswith("'d"):
            new_title += w.removesuffix("'d") + " had"
        elif w.endswith("'ll"):
            new_title += w.removesuffix("'ll") + " will"
        elif w.endswith("i'm"):
            new_title += "i am"
        else:
            new_title += w
        new_title += " "

    return new_title.strip()


__synonyms = {
    "postgres": "postgresql",
    # "c++": "cpp",
    # "c#": "csharp",
    "covid": "coronavirus",
    "covid-19": "coronavirus",
    "python4": "python",
    "python3": "python",
    "python2": "python",
    "python2.7": "python",
}


def __synonym(title):
    new_title = ""
    for w in title.split():
        if syn := __synonyms.get(w):
            new_title += syn
        else:
            new_title += w
        new_title += " "

    return new_title.strip()


def __programming_language_name(title):
    new_title = ""
    for w_tmp in title.rstrip("?").split():
        if re.match(r"^\w+[#\-+*]+$", w_tmp, flags=re.ASCII):
            w = w_tmp.replace("+", "p")
            w = w.replace("#", "sharp")
            w = w.replace("-", "m")
            w = w.replace("*", "star")
        elif re.match(r"^\.\w+$", w_tmp, flags=re.ASCII):
            w = w_tmp.replace(".", "dot")
        else:
            w = w_tmp

        new_title += w
        new_title += " "

    return new_title.strip()


def __url(title, url):
    new_title = ""
    for w in title.split():
        if w == "go" and "golang" in url:
            new_title += "golang"
        elif w == "rust" and "rustlang" in url:
            new_title += "rustlang"
        else:
            new_title += w
        new_title += " "

    return new_title.strip()


def __stem(title):
    return title

    # for w in tokens:


def __duplicate(title):
    prev = object()
    return " ".join(prev := v for v in title.split() if prev != v)


def normalize(
    title: str,
    platform: Platform | None = None,
    url: str = "",
    tags: list[str] | set[str] | None = None,
    *,
    stem: bool = True,
) -> str:
    tags = tags or []
    title = title or ""
    url = (url or "").lower()

    title = __unicode(title)

    title = " ".join(title.split())
    title = title.lower().strip()

    title = __format(title)
    title = __year(title)

    title = __contraction(title)

    title = __synonym(title)
    title = __programming_language_name(title)

    title = __punctuation(title)

    title = __synonym(title)

    if url:
        title = __url(title, url)

    match platform:
        case Platform.LOBSTERS:
            title = __lobsters(title)
        case Platform.REDDIT:
            title = __reddit(title)
        case Platform.HACKER_NEWS:
            title = __hacker_news(title)
        case Platform.LAMBDA_THE_ULTIMATE:
            title = __lambda_the_ultimate(title)
        case _:
            pass

    title = __duplicate(title)

    if stem:
        title = __stem(title)

    return title
