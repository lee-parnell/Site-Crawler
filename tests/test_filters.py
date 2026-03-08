import pytest
from crawler.filters import UrlFilter


@pytest.fixture
def f():
    return UrlFilter(
        allowed_domain="example.com",
        exclude_extensions=[".jpg", ".pdf"],
        exclude_patterns=[r"/admin/"],
        include_patterns=[],
        respect_robots=False,
    )


def test_allows_same_domain(f):
    ok, reason = f.check("https://example.com/about")
    assert ok
    assert reason == "allowed"


def test_allows_www_variant(f):
    ok, _ = f.check("https://www.example.com/about")
    assert ok


def test_rejects_other_domain(f):
    ok, reason = f.check("https://other.com/page")
    assert not ok
    assert reason == "domain"


def test_rejects_excluded_extension(f):
    ok, reason = f.check("https://example.com/photo.jpg")
    assert not ok
    assert reason == "extension"


def test_rejects_excluded_pattern(f):
    ok, reason = f.check("https://example.com/admin/users")
    assert not ok
    assert reason == "excluded"


def test_include_patterns_act_as_whitelist():
    f = UrlFilter(
        allowed_domain="example.com",
        exclude_extensions=[],
        exclude_patterns=[],
        include_patterns=[r"^/blog/"],
        respect_robots=False,
    )
    ok, _ = f.check("https://example.com/blog/post-1")
    assert ok
    ok2, reason = f.check("https://example.com/about")
    assert not ok2
    assert reason == "not_included"


def test_rejects_empty_url(f):
    ok, reason = f.check("")
    assert not ok
    assert reason == "invalid"


def test_rejects_non_http_url(f):
    ok, reason = f.check("mailto:hello@example.com")
    assert not ok
    assert reason == "invalid"
