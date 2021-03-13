from django.db import models
from django.contrib.postgres import fields as postgres_fields
from . import discussions
from django.utils import timezone
import datetime


class Discussion(models.Model):
    # class Meta:
    #     indexes = [
    #         models.Index(fields=['platform', 'archived']),
    #         models.Index(fields=['schemeless_story_url']),
    #         models.Index(fields=['canonical_story_url']),
    #         models.Index(fields=['canonical_redirect_url'])
    #     ]

    platform_id = models.CharField(primary_key=True, max_length=50)
    platform = models.CharField(max_length=1, blank=False)
    created_at = models.DateTimeField(null=True)
    scheme_of_story_url = models.CharField(max_length=25)

    """Original URL of the story without the scheme"""
    schemeless_story_url = models.CharField(max_length=100_000)
    canonical_story_url = models.CharField(max_length=100_000,
                                           blank=True,
                                           null=True)
    canonical_redirect_url = models.CharField(max_length=100_000,
                                              blank=True,
                                              default=None,
                                              null=True)

    title = models.CharField(max_length=2048)
    comment_count = models.IntegerField(default=0)
    score = models.IntegerField(default=0)

    """In case of Reddit tags will have only one entry which represents the subreddit"""
    tags = postgres_fields.ArrayField(
        models.CharField(max_length=255, blank=True), null=True, blank=True)

    archived = models.BooleanField(default=False)

    @property
    def story_url(self):
        return f"{self.scheme_of_story_url}://{self.schemeless_story_url}"

    def __str__(self):
        return f"{self.platform_id} - {self.story_url}"

    def save(self, *args, **kwargs):
        if not self.platform:
            self.platform = self.platform_id[0]

        if self.canonical_story_url == self.schemeless_story_url:
            self.canonical_story_url = None

        if (
                self.canonical_redirect_url == self.canonical_story_url or
                self.canonical_redirect_url == self.schemeless_story_url
        ):
            self.canonical_redirect_url = None

        super(Discussion, self).save(*args, **kwargs)

    @property
    def id(self):
        return self.platform_id[1:]

    @property
    def subreddit(self):
        return self.tags[0]

    @classmethod
    def platform_order(self, platform):
        if platform == 'h':
            return 1
        elif platform == 'r':
            return 2
        elif platform == 'l':
            return 3
        elif platform == 'b':
            return 4
        elif platform == 'g':
            return 5
        else:
            return 100

    @classmethod
    def platforms(cls, preferred_external_url=discussions.PreferredExternalURL.Standard):
        ps = {}
        for p in sorted(['h', 'r', 'l', 'b', 'g'], key=lambda x: cls.platform_order(x)):
            ps[p] = (cls.platform_name(p), cls.platform_url(p, preferred_external_url))
        return ps

    @classmethod
    def platform_name(cls, platform):
        if platform == 'h':
            return 'Hacker News'
        elif platform == 'r':
            return 'Reddit'
        elif platform == 'l':
            return 'Lobsters'
        elif platform == 'b':
            return 'Barnacles'
        elif platform == 'g':
            return "Gambero"

    @classmethod
    def platform_url(cls, platform, preferred_external_url):
        if platform == 'r':
            if preferred_external_url == discussions.PreferredExternalURL.Standard:
                return 'https://www.reddit.com'
            if preferred_external_url == discussions.PreferredExternalURL.Old:
                return 'https://old.reddit.com'
            if preferred_external_url == discussions.PreferredExternalURL.Mobile:
                return 'https://m.reddit.com'
        elif platform == 'h':
            return "https://news.ycombinator.com"
        elif platform == 'l':
            return "https://lobste.rs"
        elif platform == 'b':
            return "https://barnacl.es"
        elif platform == 'g':
            return "https://gambe.ro"

    @classmethod
    def platform_tag_url(cls, platform, preferred_external_url):
        if platform == 'r':
            if preferred_external_url == discussions.PreferredExternalURL.Standard:
                return 'https://www.reddit.com/r'
            if preferred_external_url == discussions.PreferredExternalURL.Old:
                return 'https://old.reddit.com/r'
            if preferred_external_url == discussions.PreferredExternalURL.Mobile:
                return 'https://m.reddit.com/r'
        elif platform == 'l':
            return "https://lobste.rs/t"
        elif platform == 'b':
            return "https://barnacl.es/t"
        elif platform == 'g':
            return "https://gambe.ro/t"

    def discussion_url(self, preferred_external_url=discussions.PreferredExternalURL.Standard):
        bu = self.platform_url(self.platform, preferred_external_url)
        if self.platform == 'r':
            return f"{bu}/r/{self.subreddit}/comments/{self.id}"
        elif self.platform == 'h':
            return f"{bu}/item?id={self.id}"
        elif self.platform in ('l', 'b', 'g'):
            return f"{bu}/s/{self.id}"

    def subreddit_name(self):
        return f"/r/{self.subreddit}"

    def subreddit_url(self, preferred_external_url=discussions.PreferredExternalURL.Standard):
        return f"{self.platform_url(self.platform, preferred_external_url)}/r/{self.subreddit}"

    @classmethod
    def of_url(cls, url, client=None):
        _, url = discussions.split_scheme(url)
        cu = discussions.canonical_url(url)
        rcu = discussions.canonical_url(url, client=client, follow_redirects=True)

        ds = (cls.objects.filter(schemeless_story_url=url) |
              cls.objects.filter(schemeless_story_url=cu) |
              cls.objects.filter(schemeless_story_url=rcu) |
              cls.objects.filter(canonical_story_url=cu) |
              cls.objects.filter(canonical_redirect_url=rcu)).order_by('platform', '-created_at', 'tags__0', '-platform_id')

        return ds, cu, rcu

    @classmethod
    def delete_useless_discussions(cls):
        three_months_ago = timezone.now() - datetime.timedelta(days=30 * 3)
        (cls.objects
         .filter(platform='r')
         .filter(archived=True)
         .filter(comment_count=0) |
         cls.objects
         .filter(platform='h')
         .filter(comment_count=0)
         .filter(created_on__lte=three_months_ago) |
         cls.objects
         .filter(platform='l')
         .filter(comment_count=0)
         .filter(created_on__lte=three_months_ago) |
         cls.objects
         .filter(platform='b')
         .filter(comment_count=0)
         .filter(created_on__lte=three_months_ago) |
         cls.objects
         .filter(platform='g')
         .filter(comment_count=0)
         .filter(created_on__lte=three_months_ago)
         ).delete()
