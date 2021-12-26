import re
import nltk
import unicodedata


def __lobsters(title):
    title = title.removeprefix('show lobsters ')
    title = title.removeprefix('show lobste.rs ')
    title = title.removeprefix('show lobste rs ')
    return title


def __reddit(title):
    return title


def __hacker_news(title):
    title = title.removeprefix('show hn ')
    title = title.removeprefix('ask hn ')
    title = title.removeprefix('tell hn ')
    title = title.strip()
    return title


def __lambda_the_ultimate(title):
    return title


def __unicode(title):
    title = unicodedata.normalize('NFKC', title)
    table = str.maketrans({
        "’": "'",
        '“': '"',
        '”': '"',
        "–": "-"
    })
    title = title.translate(table)
    return title


def __year(title):
    if re.search(r'\(1|2\d\d\d\)$', title):
        title = title[:-len('(1234)')]
    title = title.strip()
    return title


def __format(title):
    title = title.removesuffix('[pdf]')
    title = title.removesuffix('[video]')
    title = title.strip()
    return title


def __punctuation(title):
    title = title.replace("'s ", ' ')
    new_title = ""
    for c in title:
        cat = unicodedata.category(c)
        if cat.startswith('P'):
            new_title += ' '
            continue
        new_title += c
    new_title = ' '.join(new_title.split())
    return new_title


def __contraction(title):
    new_title = ""
    for w in title.split():
        if w == "isn't":
            new_title += "is not"
        elif w == "won't":
            new_title += "will not"
        elif w == "can't" or w == "cannot":
            new_title += "can not"
        elif w.endswith("'re"):
            new_title += w.removesuffix("'re") + ' are'
        elif w.endswith("'d"):
            new_title += w.removesuffix("'d") + ' had'
        elif w.endswith("'ll"):
            new_title += w.removesuffix("'ll") + ' will'
        elif w.endswith("i'm"):
            new_title += 'i am'
        else:
            new_title += w
        new_title += ' '

    return new_title.strip()


__synonyms = {
    "postgres": "postgresql",
    "c++": "cpp",
    "c#": "csharp",
    "covid": "coronavirus",
    "covid-19": "coronavirus",
    "python4": "python",
    "python3": "python",
    "python2": "python",
    "python2.7": "python"
}


def __synonym(title):
    new_title = ""
    for w in title.split():
        if syn := __synonyms.get(w):
            new_title += syn
        else:
            new_title += w
        new_title += ' '

    return new_title.strip()


def __url(title, url):
    new_title = ""
    for w in title.split():
        if w == 'go' and 'golang' in url:
            new_title += 'golang'
        elif w == 'rust' and 'rustlang' in url:
            new_title += 'rustlang'
        else:
            new_title += w
        new_title += ' '

    return new_title.strip()


def __stem(title):
    new_title = ""
    stemmer = nltk.stem.snowball.SnowballStemmer("english")
    tokens = nltk.tokenize.word_tokenize(title)

    for w in tokens:
        new_title += ' '
        new_title += stemmer.stem(w)

    return new_title.strip()


def __duplicate(title):
    prev = object()
    return ' '.join((prev := v for v in title.split() if prev != v))


def normalize(title, platform=None, url="", tags=[], stem=True):
    title = title or ''
    url = (url or '').lower()

    title = __unicode(title)

    title = ' '.join(title.split())
    title = title.lower().strip()

    title = __format(title)
    title = __year(title)

    title = __contraction(title)

    title = __synonym(title)

    title = __punctuation(title)

    title = __synonym(title)

    if url:
        title = __url(title, url)

    if platform == 'l':
        title = __lobsters(title)
    elif platform == 'r':
        title = __reddit(title)
    elif platform == 'h':
        title = __hacker_news(title)
    elif platform == 'u':
        title = __lambda_the_ultimate(title)

    title = __duplicate(title)

    if stem:
        title = __stem(title)

    return title
