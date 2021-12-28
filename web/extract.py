from collections import namedtuple

Author = namedtuple('Author', ['name',
                               'twitter_account',
                               'homepage'])

# Page type:
#   Article
#   ArticleIndex
#   wikipedia
#   Github


class Structure:
    type = None
    title = None
    article = None
    tags = None
    number_of_comments = None
    commnets_seciton = None
    permanent_url = None
    publication_date = None
    edit_date = None
    author = None


def structure(h):
    s = Structure()

    try:
        articles = h.select('article')
        if len(articles) == 1:
            s.article = articles[0]
    except Exception:
        pass

    if s.article:
        try:
            s.title = s.article.select_one('h1, h2, h3').get_text().strip()
        except Exception:
            pass

    if not s.title:
        try:
            s.title = h.select_one('title').get_text().strip()
        except Exception:
            pass

    return s
