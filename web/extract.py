from . import http
import urllib
import logging

logger = logging.getLogger(__name__)


class Author:
    name = None
    twitter_account = None
    twitter_site = None
    mastodon_account = None
    mastodon_site = None
    homepage = None


# Page type:
#   Article
#   ArticleIndex
#   wikipedia
#   Github
#   Video (Viemo, youtube, streamja, etc.)


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
    outbound_links = []


def __extract_author(article, h):
    author = Author()

    if h:
        author.twitter_account = (
            h.select_one(
                'meta[name="twitter:creator"], meta[property="twitter:creator"]'
            )
            or {}
        ).get("content", "").removeprefix("@") or None

        author.twitter_site = (
            h.select_one(
                'meta[name="twitter:site"], meta[property="twitter:site"]'
            )
            or {}
        ).get("content", "").removeprefix("@") or None

    if author.twitter_account:
        parts = author.twitter_account.split("/")
        parts = [p for p in parts if p]
        author.twitter_account = parts[-1]
        author.twitter_account = author.twitter_account.strip()

        author.twitter_account = author.twitter_account.removeprefix("@")

        if " " in author.twitter_account:
            author.twitter_account = None

    if author.twitter_site:
        parts = author.twitter_site.split("/")
        parts = [p for p in parts if p]
        author.twitter_site = parts[-1]
        author.twitter_site = author.twitter_site.strip()

        author.twitter_site = author.twitter_site.removeprefix("@")

        if " " in author.twitter_site:
            author.twitter_site = None

    # if not author.twitter_account:
    #     domain = 'twitter.com'
    #     twitter_links = []
    #     if article:
    #         twitter_links = article.select(f'a[href*="{domain}" i]')
    #     if h:
    #         twitter_links.extend(h.select(f'a[href*="{domain}" i]'))
    #     possible_accounts = set()

    #     for t in twitter_links:
    #         l = t.get('href', '')
    #         l = l.removeprefix('https://')
    #         l = l.removeprefix('http://')
    #         parts = l.split('/')
    #         parts = [p for p in parts if p]
    #         if len(parts) == 2:
    #             if parts[0] not in ('twitter.com', 'm.twitter.com', 'mobile.twitter.com', 'www.twitter.com'):
    #                 continue
    #             if '?' in parts[1] or '&' in parts[1]:
    #                 continue
    #             if parts[1] in ('signup', 'login', 'signin', 'about', 'share'):
    #                 continue
    #             possible_accounts.add(parts[1])

    #     if len(possible_accounts) == 1:
    #         author.twitter_account = possible_accounts.pop()
    #         if author.twitter_account.lower() == (author.twitter_site or '').lower():
    #             author.twitter_account = None

    return author


def structure(h):
    if type(h) == str:
        h = http.parse_html(h, safe_html=True)

    s = Structure()

    try:
        articles = h.select("article")
        if len(articles) == 1:
            s.article = articles[0]
    except Exception:
        pass

    if s.article:
        # try:
        #     s.title = s.article.select_one("h1, h2, h3").get_text().strip()
        # except Exception:
        #     pass

        try:
            s.outbound_links = s.article.select("a") or []
        except Exception:
            pass

    try:
        s.author = __extract_author(s.article, h)
    except Exception as e:
        print(f"author: {e}")
        logging.debug(f"author: {e}")
        pass

    if not s.title:
        try:
            s.title = h.select_one("title").get_text().strip()
        except Exception:
            pass

    return s


def _fetch_parse_extract(u):
    r = http.fetch(u)
    h = http.parse_html(r)
    s = structure(h)
    return s


def get_github_user_twitter(url):
    if not url:
        return

    u = None
    try:
        u = urllib.parse.urlparse(url)
    except Exception:
        return

    if not u:
        return

    if u.netloc != "github.com" and u.netloc != "www.github.com":
        return

    if not u.path:
        return

    parts = u.path.split("/")

    if len(parts) < 3:
        return

    api_url = f"https://api.github.com/repos/{parts[1]}/{parts[2]}"

    response = http.fetch(
        api_url, timeout=30, with_retries=False, with_cache=True
    )

    if not response or not response.ok:
        return

    js = response.json()
    if not js.get("owner"):
        return

    if not js.get("owner").get("url"):
        return

    response = http.fetch(
        js.get("owner").get("url"),
        timeout=30,
        with_retries=False,
        with_cache=True,
    )
    if not response or not response.ok:
        return

    return response.json().get("twitter_username")
