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
            n('old pdf (1981) [pdf]')
        ], [
            'national park typeface',
            'a',
            'cool project',
            'show hn: second project',
            'q?',
            'old pdf'
        ])
