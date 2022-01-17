from web import title as web_title


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
        if keyword.lower() not in title.lower().split():
            return tags

    return tags | {new_tag}


def __replace_tag(tags, old_tag, new_tag):
    if old_tag not in tags:
        return tags

    return (tags - {old_tag}) | {new_tag}


def __lobsters(tags, title):
    tags -= {'ask', 'audio', 'book',
             'pdf', 'show', 'slides',
             'transcript',  'video',
             'announce', 'interview', 'meta'}

    tags = __augment_tags(title, tags, None,
                          {'api', 'debugging', 'performance', 'devops', 'privacy', 'practices', 'practices', 'scaling', 'security', 'testing', 'virtualization'},
                          'programming')

    tags = __augment_tags(title, tags, None,
                          {'ai', 'distributed', 'formalmethods',
                           'graphics', 'networking', 'osdev',
                           'plt'},
                          'compsci')

    return tags


def __reddit(tags, title):
    tags = __augment_tags(title, tags, None,
                          {'soccer', 'nfl', 'chess', 'nba',
                           'hockey', 'formula1', 'baseball',
                           'wrestling', 'mma'},
                          'sport')
    tags = __augment_tags(title, tags, None,
                          {'nfl'},
                          'football')
    tags = __augment_tags(title, tags, None,
                          {'nba'},
                          'basketball')
    tags = __augment_tags(title, tags, None,
                          {'apple'},
                          'technology')
    tags = __augment_tags(title, tags, None,
                          {'spacex'},
                          'space')
    tags = __augment_tags(title, tags, None,
                          {'laravel'},
                          'php')
    return tags


def __hacker_news(tags, title):
    tags = __augment_tags(title, tags, 'python')
    tags = __augment_tags(title, tags, 'docker')
    tags = __augment_tags(title, tags, 'javascript')
    tags = __augment_tags(title, tags, 'typescript')
    tags = __augment_tags(title, tags, 'lisp')
    tags = __augment_tags(title, tags, 'rust', None, 'rustlang')
    return tags


def __lambda_the_ultimate(tags, title):
    return tags - {'previously', 'general', 'recent discussion', 'previously on ltu', 'discussion', 'recently', 'here'}


def __laarc(tags, title):
    return tags - {'news', 'meta', 'laarc', 'ask'}


def __from_title_url(tags, title, url):
    tags = __augment_tags(title, tags, 'golang')
    tags = __augment_tags(title, tags, 'rustlang')
    tags = __augment_tags(title, tags, 'rust', {'programming'}, 'rustlang')
    tags = __augment_tags(title, tags, 'cpp')
    tags = __augment_tags(title, tags, 'csharp')
    tags = __augment_tags(title, tags, 'haskell')
    tags = __augment_tags(title, tags, 'java', {'programming'})
    tags = __augment_tags(title, tags, 'django', {'python', 'webdev', 'programming'})
    tags = __augment_tags(title, tags, 'flask', {'python', 'webdev', 'programming'})
    tags = __augment_tags(title, tags, 'linux')
    tags = __augment_tags(title, tags, 'dragonflybsd')
    tags = __augment_tags(title, tags, 'freebsd')
    tags = __augment_tags(title, tags, 'netbsd')
    tags = __augment_tags(title, tags, 'openbsd')
    tags = __augment_tags(title, tags, 'spacex')

    if 'swift' in title.split() and ('swift.org' in url or 'swiftlang' in url):
        tags |= {'swiftlang'}

    return tags


def __rename(tags, title, platform=None):
    to_replace = [('rust', 'rustlang'),
                  ('go', 'golang'),
                  ('c++', 'cpp'),
                  ('.net', 'dotnet'),
                  ('c#', 'csharp'),
                  ('swift', 'swiftlang'),
                  ('web', 'webdev', 'l'),
                  ('d', 'dlang', 'l'),
                  ('coding', 'programming', 'r'),
                  ('c_programming', 'c', 'r'),
                  ('d_language', 'dlang', 'r'),
                  ('btc', 'bitcoin', 'r'),
                  ('worldevents', 'news', 'r'),
                  ('worldnews', 'news', 'r'),
                  ('upliftingnews', 'news', 'r'),
                  ('moderatepolitics', 'politics', 'r'),
                  ('internationalpolitics', 'politics', 'r'),
                  ('sports', 'sport', 'r'),
                  ('web_design', 'webdesign', 'r'),
                  ('reddit.com', 'reddit', 'r'),
                  ('squaredcircle', 'wrestling', 'r'),
                  ('europes', 'europe', 'r'),
                  ('ml', 'ocaml', 'l')]
    for p in to_replace:
        if len(p) == 3 and p[2] != platform:
            continue
        tags = __replace_tag(tags, p[0], p[1])

    return tags


def __enrich(tags, title):
    tags = __augment_tags(title, tags, None,
                          {'python', 'rustlang', 'golang',
                           'haskell', 'cpp', 'lisp', 'scheme',
                           'swiftlang', 'apl', 'assembly',
                           'cprogramming', 'clojure',
                           'dlang', 'dotnet', 'elixir',
                           'elm', 'erlang', 'fortran',
                           'java', 'javascript', 'typescript',
                           'lua',
                           'ocaml', 'nodejs', 'objectivec',
                           'perl', 'php', 'scala', 'zig'},
                          'programming')

    tags = __augment_tags(title, tags, None,
                          {'django', 'flask'},
                          'python')
    tags = __augment_tags(title, tags, None,
                          {'django', 'flask', 'javascript', 'typescript'},
                          'webdev')

    tags = __augment_tags(title, tags, None,
                          {'linux', 'dragonflybsd', 'freebsd', 'netbsd', 'openbsd'},
                          'unix')

    tags = __augment_tags(title, tags, None,
                          {'docker', 'kubernets'},
                          'devops')

    return tags


def normalize(tags, platform=None, title="", url=""):
    tags = tags or []
    tags = set(t.lower().strip() for t in tags)
    title = web_title.normalize(title, platform, url, tags, stem=False)
    url = url.lower()

    for _ in range(3):
        tags = __from_title_url(tags, title, url)

        if platform == 'l':
            tags = __lobsters(tags, title)
        elif platform == 'r':
            tags = __reddit(tags, title)
        elif platform == 'h':
            tags = __hacker_news(tags, title)
        elif platform == 'a':
            tags = __laarc(tags, title)
        elif platform == 'u':
            tags = __lambda_the_ultimate(tags, title)

        tags = __rename(tags, title, platform)
        tags = __enrich(tags, title)

    return sorted(list(tags))
