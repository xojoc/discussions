from web import models, topics
import logging

logger = logging.getLogger(__name__)


def get_reading_list(topic, category):
    t = topics.topics.get(topic)
    if not t:
        return None

    tags = "".join(t.get("tags", set()))
    platform = t.get("platform", "")

    subquery_where = ""
    if tags:
        subquery_where = """
        array(select unnest(normalized_tags)
            from web_discussion wd
            where
                wd.canonical_story_url = web_discussion.canonical_story_url)
                && array[%(tags)s]::varchar[]"""
    elif platform:
        subquery_where = """
        %(platform)s in (select platform
            from web_discussion wd
            where
                wd.canonical_story_url = web_discussion.canonical_story_url)"""

    stories = models.Discussion.objects.raw(
        f"""
 with web_discussion_quartile as (
    select
        ntile(100) over(partition by platform order by score, comment_count) score_quartile,
        web_discussion_total.total_comments,
        web_discussion_total.total_discussions,
        *
    from web_discussion
        left join lateral
        (select sum(comment_count) as total_comments,
                count(*) as total_discussions
            from web_discussion wd
                where
                wd.canonical_story_url = web_discussion.canonical_story_url and
                wd.comment_count >= 2 and
                wd.score >= 2
        ) as web_discussion_total on true
     where
    {subquery_where}
 and %(category)s in (select category
            from web_discussion wd
            where
                wd.canonical_story_url = web_discussion.canonical_story_url)
 and comment_count >= 100
 and score >= 100
)
select *
from web_discussion_quartile
where
score_quartile = 100
order by platform, score desc, comment_count desc
""",
        {"tags": tags, "platform": platform, "category": category},
    )

    return stories


def get_reading_list_cached(topic, category):
    return get_reading_list(topic, category)
