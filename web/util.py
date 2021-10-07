from urllib.parse import quote as quote_url


def discussions_url(story_url):
    return 'https://discussions.xojoc.pw/?url=' + quote_url(story_url)
