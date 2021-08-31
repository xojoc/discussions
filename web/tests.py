import unittest
from web import discussions


class Discussions(unittest.TestCase):
    def test_canonical_url(self):
        c = discussions.canonical_url
        self.assertEqual([c('https://medium.com/swlh/caching-and-scaling-django-dc80a54012'),
                          c("http://www.path-normalization.com/a///index.html////"),
                          c("https://www.youtube.com/watch?v=71SsVUmT1ys&ignore=query"),
                          c("https://www.youtube.com/embed/71SsVUmT1ys?ignore=query"),
                          c("https://www.xojoc.pw/blog/////focus.html"),
                          c("https://web.archive.org/web/20200103092739/https://www.xojoc.pw/blog/focus.html"),
                          c("https://twitter.com/#!wikileaks/status/1255304335887646721"),
                          c("https://github.com/xojoc/discussions/tree/master"),
                          c("https://groups.google.com/forum/#!topic/mozilla.dev.platform/1PHhxBxSehQ"),


                          ],
                         ['medium.com/p/dc80a54012',
                          'path-normalization.com/a',
                          'youtu.be/71SsVUmT1ys',
                          'youtu.be/71SsVUmT1ys',
                          'xojoc.pw/blog/focus',
                          'xojoc.pw/blog/focus',
                          'twitter.com/wikileaks/status/1255304335887646721',
                          'github.com/xojoc/discussions',
                          'groups.google.com/g/mozilla.dev.platform/c/1PHhxBxSehQ'])
