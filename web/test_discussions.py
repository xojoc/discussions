from django.test import Client, TestCase
import urllib

from web import models, http


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
        self.assertEqual(response.status_code, 404)

        response = self.client.get("/", {"q": "title"})
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/", {"url": "title"})
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/q/title")
        self.assertEqual(response.status_code, 200)

        response = self.client.get(
            "/", {"q": "https://example.com", "submit_title": "Submit Title"}
        )
        qu = urllib.parse.quote("https://example.com")
        h = http.parse_html(response.content)
        submit_links = h.select(f".submit_links details ul li a[href*='{qu}']")
        self.assertTrue(len(submit_links) >= 1)
