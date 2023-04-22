import unittest

from web import hn


class UnitHN(unittest.TestCase):
    def test_selftext_url(self):
        tests = [
            """Connect two articles on Wikipedia, but do it the long way.
            I&#x27;ve always been a fan of the theory of six degree of separation,
            but it&#x27;s an overused concept when exploring the Wiki-graph.<p>Instead of showing the shortest path,
            which in my opinion is &quot;boring&quot; and ends up connecting super-important central articles,
             I came up with my own method: WikiBinge selects the smaller, less represented articles on Wikipedia.
             In a WikiBinge path, the underdogs are the kings!<p>How does it work? It&#x27;s pretty straightforward!
             Compute PageRank on the Wiki-graph and assign as weight of each edge the PageRank value of the destination node.
             A WikiBinge path is then simply a shortest path using these weights: the algorithm will then favor paths passing through
             articles with lower PageRank values.<p>More on the motives to build this here:
              <a href=\"https:&#x2F;&#x2F;www.jamez.it&#x2F;project&#x2F;wikibinge&#x2F;\" rel=\"nofollow\">https:&#x2F;&#x2F;www.jamez.it&#x2F;project&#x2F;wikibinge&#x2F;</a>
              <p>This is an older project of mine, but it never got much exposure, so I&#x27;m humbly submitting it now.""",
            "https://www.jamez.it/project/wikibinge/",
        ]
        for h, u in zip(tests[0::2], tests[1::2]):
            hu = hn._url_from_selftext(h)
            assert u == hu, h
