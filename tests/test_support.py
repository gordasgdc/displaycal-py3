"""Support and feedback helpers: voluntary, redacted, no hidden transmission."""

import os

from DisplayCAL import support


def test_star_url_is_the_fork_page():
    assert support.REPO_URL == "https://github.com/gordasgdc/displaycal-py3"


def test_credits_links_stay_separate_from_the_fork():
    assert "eoyilmaz" in support.UPSTREAM_URL
    assert support.ORIGINAL_URL == "https://displaycal.net/"
    assert support.REPO_URL not in (support.UPSTREAM_URL, support.ORIGINAL_URL)


def test_redact_removes_identifying_data(monkeypatch):
    monkeypatch.setenv("USER", "cristi")
    home = os.path.expanduser("~")
    text = (
        f"open {home}/Library/x.log by cristi mail cristi@example.com "
        "ip 192.168.1.20 serial: 0123456789 id 0123456789abcdef0123456789abcdef "
        "token=abc123"
    )
    out = support.redact(text)
    for leaked in (
        "cristi",
        "192.168.1.20",
        "0123456789abcdef",
        "abc123",
        "example.com",
    ):
        assert leaked not in out.lower() or leaked == "cristi" and "<user>" in out
    assert "~/Library" in out and "<ip>" in out and "<email>" in out


def test_issue_url_shows_version_and_platform_in_body():
    url, cut = support.build_issue_url("problem", "It crashes at step 4")
    assert url.startswith(support.ISSUES_NEW_URL + "?title=")
    assert "Version" in url and "Platform" in url and not cut


def test_diagnostic_only_when_given_and_url_stays_bounded():
    without, _ = support.build_issue_url("suggestion", "idea")
    assert "Diagnostic" not in without
    big = "x" * 50_000
    with_diag, cut = support.build_issue_url("problem", "bug", big)
    assert "Diagnostic" in with_diag and cut
    assert len(with_diag) <= support.MAX_URL_LEN + 200


def test_collect_diagnostic_is_redacted(tmp_path, monkeypatch):
    monkeypatch.setenv("USER", "cristi")
    log = tmp_path / "x.log"
    log.write_text("line cristi@example.com\nfine\n", encoding="utf-8")
    text = support.collect_diagnostic(str(log))
    assert "example.com" not in text and "fine" in text
