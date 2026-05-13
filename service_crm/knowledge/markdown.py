"""Tiny safe-by-default Markdown renderer.

Covers the subset relevant for v0.6 procedures: headings (``#``..``####``),
paragraphs, ordered + unordered lists, fenced code blocks, inline
``code``, ``**bold**`` / ``*italic*``, and ``[label](url)`` links with
an allowlist of schemes (``http``, ``https``, ``mailto``). Anything else
falls through as escaped plain text — there is **no** raw-HTML pass-through.

Why hand-rolled and not ``markdown-it-py``: keeps the dep list lean and
keeps the security surface visible — every escape rule is in this file.
Table and image support are deferred to a later milestone if the
product demands them.
"""

from __future__ import annotations

import re
from html import escape

_HEADING_RE = re.compile(r"^(#{1,4})\s+(.*)$")
_FENCED_RE = re.compile(r"^```(\S*)\s*$")
_OL_RE = re.compile(r"^\s*\d+\.\s+(.+)$")
_UL_RE = re.compile(r"^\s*[-*]\s+(.+)$")
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
_BOLD_RE = re.compile(r"\*\*([^*\n]+)\*\*")
_ITALIC_RE = re.compile(r"(?<![*\w])\*([^*\n]+)\*(?![*\w])")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")

_ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https", "mailto"})


def render(body: str) -> str:
    """Render ``body`` to safe HTML. Empty input returns ``""``."""
    if not body:
        return ""
    lines = body.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return _render_block(lines)


def _render_block(lines: list[str]) -> str:
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]

        fenced = _FENCED_RE.match(line)
        if fenced is not None:
            i, html = _consume_code(lines, i, language=fenced.group(1))
            out.append(html)
            continue

        head = _HEADING_RE.match(line)
        if head is not None:
            level = len(head.group(1))
            text = _render_inline(head.group(2).strip())
            out.append(f"<h{level}>{text}</h{level}>")
            i += 1
            continue

        if _UL_RE.match(line):
            i, html = _consume_list(lines, i, ordered=False)
            out.append(html)
            continue
        if _OL_RE.match(line):
            i, html = _consume_list(lines, i, ordered=True)
            out.append(html)
            continue

        if line.strip() == "":
            i += 1
            continue

        i, html = _consume_paragraph(lines, i)
        out.append(html)

    return "\n".join(out)


def _consume_code(lines: list[str], start: int, *, language: str) -> tuple[int, str]:
    body: list[str] = []
    i = start + 1
    while i < len(lines):
        if _FENCED_RE.match(lines[i]):
            i += 1
            break
        body.append(lines[i])
        i += 1
    code = "\n".join(body)
    cls = f' class="lang-{escape(language)}"' if language else ""
    return i, f"<pre><code{cls}>{escape(code)}</code></pre>"


def _consume_list(lines: list[str], start: int, *, ordered: bool) -> tuple[int, str]:
    pattern = _OL_RE if ordered else _UL_RE
    tag = "ol" if ordered else "ul"
    items: list[str] = []
    i = start
    while i < len(lines):
        match = pattern.match(lines[i])
        if match is None:
            break
        items.append(f"<li>{_render_inline(match.group(1).strip())}</li>")
        i += 1
    return i, f"<{tag}>{''.join(items)}</{tag}>"


def _consume_paragraph(lines: list[str], start: int) -> tuple[int, str]:
    body: list[str] = []
    i = start
    while i < len(lines):
        line = lines[i]
        if (
            line.strip() == ""
            or _HEADING_RE.match(line)
            or _FENCED_RE.match(line)
            or _UL_RE.match(line)
            or _OL_RE.match(line)
        ):
            break
        body.append(line.rstrip())
        i += 1
    text = _render_inline(" ".join(body).strip())
    return i, f"<p>{text}</p>"


def _render_inline(text: str) -> str:
    escaped = escape(text)
    # Inline code is rendered first so its contents don't get bold /
    # italic / link substitutions.
    parts: list[str] = []
    last = 0
    for match in _INLINE_CODE_RE.finditer(escaped):
        parts.append(_apply_emphasis_and_links(escaped[last : match.start()]))
        parts.append(f"<code>{match.group(1)}</code>")
        last = match.end()
    parts.append(_apply_emphasis_and_links(escaped[last:]))
    return "".join(parts)


def _apply_emphasis_and_links(text: str) -> str:
    # Emphasis runs *before* link substitution so a URL like
    # ``http://ex.com/a*b*c`` can't have its ``href`` corrupted by the
    # italic regex. Emphasis inside link labels still renders because
    # ``[**bold**](url)`` becomes ``[<strong>bold</strong>](url)``
    # before the link regex consumes the brackets.
    text = _BOLD_RE.sub(r"<strong>\1</strong>", text)
    text = _ITALIC_RE.sub(r"<em>\1</em>", text)
    text = _LINK_RE.sub(_link_sub, text)
    return text


def _link_sub(match: re.Match[str]) -> str:
    label = match.group(1)
    url = match.group(2)
    if not _is_safe_url(url):
        return f"{label} ({url})"
    return f'<a href="{url}" rel="noopener noreferrer">{label}</a>'


def _is_safe_url(url: str) -> bool:
    if "://" in url:
        scheme = url.split("://", 1)[0].lower()
        return scheme in _ALLOWED_SCHEMES
    if url.startswith("mailto:"):
        return True
    # Reject anything else that starts with a scheme-like prefix
    # (``foo:``) — ``javascript:``, ``data:``, ``file:`` would all be
    # rejected here. Same-origin relatives have no ``:`` before the path.
    if ":" in url.split("/", 1)[0]:
        return False
    # Reject protocol-relative URLs.
    return not url.startswith("//")


__all__ = ["render"]
