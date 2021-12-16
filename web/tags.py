def __augment_tags(title, tags, keyword, atleast_tags=None, new_tag=None):
    if atleast_tags:
        if len(tags & atleast_tags) == 0:
            return tags

    if not new_tag and keyword:
        new_tag = keyword.lower()

    if not new_tag:
        return tags

    if new_tag in tags:
        return tags

    if keyword:
        if keyword.lower() not in title.lower().split(' '):
            return tags

    return tags | {new_tag}


def __replace_tag(tags, old_tag, new_tag):
    if old_tag not in tags:
        return tags

    return (tags - {old_tag}) | {new_tag}


def __lobsters(tags, title):
    return tags


def __reddit(tags, title):
    return tags


def __hacker_news(tags, title):
    tags = __augment_tags(title, tags, 'python')
    return tags


def __lambda_the_ultimate(tags, title):
    return tags


def __from_title(tags, title):
    # todo: use wikidata to extrapolate tag from title?
    return tags


def __rename(tags, title):
    to_replace = [('rust', 'rustlang'), ('go', 'golang'),
                  ('c++', 'cpp'), ('.net', 'dotnet'),
                  ('c#', 'csharp')]
    for p in to_replace:
        tags = __replace_tag(tags, p[0], p[1])

    return tags


def __enrich(tags, title):
    tags = __augment_tags(title, tags, 'django',
                          {'python', 'web', 'webdev', 'programming'})
    tags = __augment_tags(title, tags, 'flask',
                          {'python', 'web', 'webdev', 'programming'})

    tags = __augment_tags(title, tags, None,
                          {'python', 'rustlang', 'golang', 'haskell', 'cpp'},
                          'programming')

    tags = __augment_tags(title, tags, None,
                          {'django', 'flask'},
                          'python')

    return tags


def normalize(tags, platform=None, title="", url=""):
    tags = tags or []
    tags = set(t.lower().strip() for t in tags)
    title = title.lower()

    for _ in range(3):
        if platform == 'l':
            tags = __lobsters(tags, title)
        elif platform == 'r':
            tags = __reddit(tags, title)
        elif platform == 'h':
            tags = __hacker_news(tags, title)
        elif platform == 'u':
            tags = __lambda_the_ultimate(tags, title)

        tags = __rename(tags, title)
        tags = __enrich(tags, title)

    return sorted(list(tags))
