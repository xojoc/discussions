import unittest
from web import discussions


class Discussions(unittest.TestCase):
    def test_canonical_url(self):
        c = discussions.canonical_url
        self.assertEqual([c('https://medium.com/swlh/caching-and-scaling-django-dc80a54012'),
                          c('https://bgolus.medium.com/the-quest-for-very-wide-outlines-ba82ed442cd9'),
                          c("http://www.path-normalization.com/a///index.html////"),
                          c("https://www.youtube.com/watch?v=71SsVUmT1ys&ignore=query"),
                          c("https://www.youtube.com/embed/71SsVUmT1ys?ignore=query"),
                          c("https://www.xojoc.pw/blog/////focus.html"),
                          c("https://web.archive.org/web/20200103092739/https://www.xojoc.pw/blog/focus.html"),
                          c("https://twitter.com/#!wikileaks/status/1255304335887646721"),
                          c("https://github.com/xojoc/discussions/tree/master"),
                          c("https://groups.google.com/forum/#!topic/mozilla.dev.platform/1PHhxBxSehQ"),
                          c("www.nytimes.com/2006/10/11/technology/11yahoo.html?ex=1318219200&en=538f73d9faa9d263&ei=5090&partner=rssuserland&emc=rss"),
                          c("https://open.nytimes.com/tracking-covid-19-from-hundreds-of-sources-one-extracted-record-at-a-time-dd8cbd31f9b4"),
                          c("www.techcrunch.com/2009/05/30/vidoop-is-dead-employees-getting-computers-in-lieu-of-wages/?awesm=tcrn.ch_2t3&utm_campaign=techcrunch&utm_content=techcrunch-autopost&utm_medium=tcrn.ch-twitter&utm_source=direct-tcrn.ch")
                          ],
                         ['medium.com/p/dc80a54012',
                          'bgolus.medium.com/ba82ed442cd9',
                          'path-normalization.com/a',
                          'youtu.be/71SsVUmT1ys',
                          'youtu.be/71SsVUmT1ys',
                          'xojoc.pw/blog/focus',
                          'xojoc.pw/blog/focus',
                          'twitter.com/wikileaks/status/1255304335887646721',
                          'github.com/xojoc/discussions',
                          'groups.google.com/g/mozilla.dev.platform/c/1PHhxBxSehQ',
                          'nytimes.com/2006/10/11/technology/11yahoo',
                          'open.nytimes.com/dd8cbd31f9b4',
                          'techcrunch.com/2009/05/30/vidoop-is-dead-employees-getting-computers-in-lieu-of-wages'])
