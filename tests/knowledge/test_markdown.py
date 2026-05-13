"""Unit tests for the in-package Markdown renderer."""

from __future__ import annotations

import pytest

from service_crm.knowledge.markdown import render


def test_empty_input() -> None:
    assert render("") == ""


def test_paragraphs() -> None:
    html = render("Hello world.\n\nSecond para.")
    assert "<p>Hello world.</p>" in html
    assert "<p>Second para.</p>" in html


def test_headings() -> None:
    html = render("# H1\n## H2\n### H3\n#### H4")
    assert "<h1>H1</h1>" in html
    assert "<h2>H2</h2>" in html
    assert "<h3>H3</h3>" in html
    assert "<h4>H4</h4>" in html


def test_unordered_list() -> None:
    html = render("- a\n- b\n- c")
    assert html == "<ul><li>a</li><li>b</li><li>c</li></ul>"


def test_ordered_list() -> None:
    html = render("1. a\n2. b")
    assert html == "<ol><li>a</li><li>b</li></ol>"


def test_inline_code() -> None:
    html = render("Use `flask run` to start.")
    assert "<code>flask run</code>" in html


def test_bold_and_italic() -> None:
    html = render("**bold** and *italic*")
    assert "<strong>bold</strong>" in html
    assert "<em>italic</em>" in html


def test_link_safe_scheme() -> None:
    html = render("[click](https://example.com)")
    assert '<a href="https://example.com"' in html


def test_link_blocks_javascript_scheme() -> None:
    html = render("[evil](javascript:alert(1))")
    assert "<a href=" not in html
    assert "evil" in html  # label still visible


def test_link_blocks_protocol_relative() -> None:
    html = render("[x](//evil.com/path)")
    assert "<a href=" not in html


def test_link_allows_mailto() -> None:
    html = render("[mail](mailto:a@b.com)")
    assert 'href="mailto:a@b.com"' in html


def test_link_relative_url_allowed() -> None:
    html = render("[home](/dashboard)")
    assert 'href="/dashboard"' in html


def test_html_escaped() -> None:
    html = render("<script>alert(1)</script>")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_fenced_code() -> None:
    html = render("```python\nprint('hi')\n```")
    assert html.startswith('<pre><code class="lang-python">')
    assert "print(" in html  # body escaped, language preserved
    assert "</code></pre>" in html


def test_fenced_code_no_lang() -> None:
    html = render("```\nfoo\n```")
    assert "<pre><code>foo</code></pre>" in html


def test_inline_code_with_emphasis_inside_not_rendered() -> None:
    html = render("`**not bold**`")
    assert "<code>**not bold**</code>" in html
    assert "<strong>" not in html


def test_carriage_returns_normalised() -> None:
    html = render("a\r\nb\r\n\r\nc")
    assert "<p>a b</p>" in html
    assert "<p>c</p>" in html


def test_blank_lines_skipped() -> None:
    html = render("\n\n\n")
    assert html == ""


def test_paragraph_ends_at_heading() -> None:
    html = render("para text\n# next")
    assert "<p>para text</p>" in html
    assert "<h1>next</h1>" in html


@pytest.mark.parametrize(
    "src,expected",
    [
        ("**a**", "<p><strong>a</strong></p>"),
        ("*a*", "<p><em>a</em></p>"),
        ("# h", "<h1>h</h1>"),
    ],
)
def test_simple_cases(src: str, expected: str) -> None:
    assert expected in render(src)


def test_unclosed_fenced_code_block() -> None:
    # No closing ``` — the loop hits the EOF break path.
    html = render("```\nbody1\nbody2\n")
    assert "<pre><code>" in html
    assert "body1" in html
    assert "body2" in html
    assert "</code></pre>" in html


def test_list_terminates_before_other_content() -> None:
    # The list-consuming loop must break when it hits a non-list line.
    html = render("- a\n- b\nplain text")
    assert "<ul><li>a</li><li>b</li></ul>" in html
    assert "<p>plain text</p>" in html


def test_link_with_path_having_colon() -> None:
    # A relative URL with a colon inside the path (after a slash) is allowed.
    html = render("[ok](/foo/bar:baz)")
    assert 'href="/foo/bar:baz"' in html


def test_link_url_with_asterisks_not_corrupted_by_emphasis() -> None:
    # If the italic regex ran *after* link substitution, ``*b*`` inside
    # the URL would be replaced with ``<em>b</em>`` and the href would
    # break. Emphasis runs first so this round-trips cleanly.
    html = render("[link](http://ex.com/a*b*c)")
    assert 'href="http://ex.com/a*b*c"' in html
    assert "<em>" not in html
