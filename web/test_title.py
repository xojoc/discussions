from web import title
import unittest


class UnitTitle(unittest.TestCase):
    def test_normalization(self):
        n = title.normalize
        self.assertEqual(
            [
                n("National Park Typeface (2019)", stem=False),
                n("a(2021)", stem=False),
                # n('Show HN: Cool Project', platform='h'),
                n("Show HN: second Project", stem=False),
                # n('Ask HN: q?', platform='h'),
                n("old pdf (1981) [pdf]", stem=False),
                n('books\'s "title"', stem=False),
                n("“Quotes”", stem=False),
                n("Ⅷ", stem=False),
                n("isn't you're i'd we'll i'm can’t", stem=False),
                n("Postgres Plugin in c++", stem=False),
                n("Why Go 1.4.1.?", url="blog.org/why-golang", stem=False),
                n("Postgres: PostgreSQL 10 Released", stem=False),
                n("a++ A-0 c-- C* J++ J# xbase++ .ql", stem=False),
            ],
            [
                "national park typeface",
                "a",
                # 'cool project',
                "show hn second project",
                # 'q',
                "old pdf",
                "books title",
                "quotes",
                "viii",
                "is not you are i had we will i am can not",
                "postgresql plugin in cpp",
                "why golang 1.4.1",
                "postgresql 10 released",
                "app a-0 cmm cstar jpp jsharp xbasepp dotql",
            ],
        )
