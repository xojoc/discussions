from web import title
import unittest


class Title(unittest.TestCase):
    def test_normalization(self):
        n = title.normalize
        self.assertEqual([
            n('National Park Typeface (2019)'),
            n('a(2021)'),
            n('Show HN: Cool Project', platform='h'),
            n('Show HN: second Project'),
            n('Ask HN: q?', platform='h'),
            n('old pdf (1981) [pdf]'),
            n('books\'s "title"'),
            n('“Quotes”'),
            n('Ⅷ'),
            n("isn't you're i'd we'll i'm can’t")
        ], [
            'nation park typefac',
            'a',
            'cool project',
            'show hn second project',
            'q',
            'old pdf',
            'book titl',
            'quot',
            'viii',
            'is not you are i had we will i am can not'
            # 'national park typeface',
            # 'a',
            # 'cool project',
            # 'show hn second project',
            # 'q',
            # 'old pdf',
            # 'book title',
            # 'quotes',
            # 'viii',
            # 'is not you are i had we will i am can not'
        ])
