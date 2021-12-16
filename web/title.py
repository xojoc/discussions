import re


def __lobsters(title):
    title = title.removeprefix('show lobsters')
    title = title.removeprefix('show lobste.rs')
    return title


def __reddit(title):
    return title


def __hacker_news(title):
    title = title.removeprefix('show hn:')
    title = title.removeprefix('ask hn:')
    title = title.removeprefix('tell hn:')
    title = title.strip()
    return title


def __lambda_the_ultimate(title):
    return title


def __year(title):
    if re.search(r'\(\d\d\d\d\)$', title):
        title = title[:-len('(1234)')]
    title = title.strip()
    return title


def __format(title):
    title = title.removesuffix('[pdf]')
    title = title.removesuffix('[video]')
    title = title.strip()
    return title


def normalize(title, platform=None, url="", tags=[]):
    title = (title or '').lower().strip()

    title = __format(title)
    title = __year(title)

    if platform == 'l':
        title = __lobsters(title)
    elif platform == 'r':
        title = __reddit(title)
    elif platform == 'h':
        title = __hacker_news(title)
    elif platform == 'u':
        title = __lambda_the_ultimate(title)

    return title
