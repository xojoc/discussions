import urllib

from django.test import Client, TestCase

from web import http, models


class LookupTestCase(TestCase):
    def setUp(self):
        models.Discussion.objects.create(
            platform_id="h123",
            scheme_of_story_url="https",
            schemeless_story_url="example.com",
            title="Example title",
            comment_count=30,
            score=100,
        )

        self.client = Client()

    def test_parameters(self):
        response = self.client.get("/", {"q": "this title doesn't exist"})
        assert response.status_code == 404

        response = self.client.get("/", {"q": "title"})
        assert response.status_code == 200

        response = self.client.get("/", {"url": "title"})
        assert response.status_code == 200

        response = self.client.get("/q/title")
        assert response.status_code == 200

        response = self.client.get(
            "/", {"q": "https://example.com", "submit_title": "Submit Title"},
        )
        qu = urllib.parse.quote("https://example.com")
        h = http.parse_html(response.content)
        submit_links = h.select(f".submit_links details ul li a[href*='{qu}']")
        assert len(submit_links) >= 1
