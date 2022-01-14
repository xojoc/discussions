from web import title
import unittest


class Title(unittest.TestCase):
    def test_normalization(self):
        n = title.normalize
        self.assertEqual([
            n('National Park Typeface (2019)'),
            n('a(2021)'),
            # n('Show HN: Cool Project', platform='h'),
            n('Show HN: second Project'),
            # n('Ask HN: q?', platform='h'),
            n('old pdf (1981) [pdf]'),
            n('books\'s "title"'),
            n('“Quotes”'),
            n('Ⅷ'),
            n("isn't you're i'd we'll i'm can’t"),
            n("Postgres Plugin in c++"),
            n('Why Go 1.4.1.?', url='blog.org/why-golang', stem=False),
            n("Postgres: PostgreSQL 10 Released", stem=False),
            n("a++ A-0 c-- C* J++ J# xbase++ .ql", stem=False),
        ], [
            'nation park typefac',
            'a',
            # 'cool project',
            'show hn second project',
            # 'q',
            'old pdf',
            'book titl',
            'quot',
            'viii',
            'is not you are i had we will i am can not',
            'postgresql plugin in cpp',
            'why golang 1.4.1',
            'postgresql 10 released',
            'app a-0 cmm cstar jpp jsharp xbasepp dotql'
        ])
