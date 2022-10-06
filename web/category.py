import urllib3
import logging


logger = logging.getLogger(__name__)

categories = {
    "article": {
        "name": "Articles",
        "sort": 10,
    },
    "release": {
        "name": "Releases",
        "sort": 20,
    },
    "project": {
        "name": "Projects",
        "sort": 30,
    },
    "video": {
        "name": "Videos",
        "sort": 40,
    },
}


def derive(story):
    u = None
    try:
        u = urllib3.util.parse_url(story.canonical_story_url)
    except Exception as e:
        logger.warning(f"category: url parsing failed: {e}")

    path, host = "", ""
    if u:
        path = u.path or ""
        host = u.host or ""
    title_tokens = (story.normalized_title or "").split()

    if "programming" in story.normalized_tags:
        if "release" in title_tokens or "released" in title_tokens:
            return "release"
    if "release" in story.normalized_tags:
        return "release"

    parts = [p for p in path.split("/") if p]

    if host in (
        "github.com",
        "gitlab.com",
        "bitbucket.org",
        "gitea.com",
    ):
        if len(parts) == 2:
            return "project"

    if host in ("sr.ht"):
        if len(parts) == 2 and parts[0][0] == "~":
            return "project"

    if host in ("savannah.gnu.org", "savannah.nongnu.org"):
        if path.startswith("/projects/"):
            return "project"

    if host in ("crates.io"):
        if path.startswith("/crates/"):
            return "project"

    if host in ("docs.rs"):
        if len(parts) == 1:
            return "project"

    # fixme: look for parameters too
    if host in ("youtu.be", "youtube.com", "vimeo.com"):
        return "video"

    return "article"
