"""T-40 to T-42: message rendering is safe and supports the documented formatting (runs the real client code in Node)."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

HARNESS = Path(__file__).parent / "render_harness.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")


def render(*cases):
    payload = json.dumps([c if isinstance(c, dict) else {"text": c} for c in cases])
    out = subprocess.run(["node", str(HARNESS)], input=payload, capture_output=True, text=True, check=True, timeout=20)
    return json.loads(out.stdout)


def test_t40_hostile_input_is_neutralized():
    hostile = [
        "<script>alert(1)</script>",
        '<img src=x onerror="alert(1)">',
        '[click](javascript:alert(1))',
        "**<b onmouseover=alert(1)>bold</b>**",
        "`<script>`",
        "```\n<script>alert(2)</script>\n```",
        '[x](https://evil.example/" onmouseover="alert(1))',
        "<a href='javascript:alert(1)'>x</a>",
        "*<iframe src=//evil></iframe>*",
        "[a](<javascript:alert(1)>)",
    ]
    for text, html in zip(hostile, render(*hostile)):
        assert not re.search(r"<(script|img|iframe|b|a)\b[^>]*(on\w+=|src=|javascript:)", html, re.I), (text, html)
        assert "<script" not in html.lower() and "<iframe" not in html.lower() and "<img" not in html.lower(), (text, html)
        for tag in re.findall(r"<a\b[^>]*>", html):
            assert re.fullmatch(r'<a href="https?://[^" ]*" target="_blank" rel="noopener noreferrer">', tag), (text, tag)


def test_t41_supported_formatting_works():
    out = render(
        "plain & simple",
        "**bold** and *italic* and `code`",
        "line one\nline two",
        "```\nblock <b>\n```",
        {"text": "hi @alice and @nobody", "mentions": ["alice"]},
        "[docs](https://example.com/a?b=1&c=2)",
    )
    assert out[0] == "plain &amp; simple"
    assert out[1] == "<strong>bold</strong> and <em>italic</em> and <code>code</code>"
    assert out[2] == "line one<br>line two"
    assert out[3] == "<pre><code>block &lt;b&gt;\n</code></pre>"
    assert 'class="mention">@alice</span>' in out[4] and "@nobody" in out[4] and out[4].count("mention") == 1
    assert out[5] == '<a href="https://example.com/a?b=1&amp;c=2" target="_blank" rel="noopener noreferrer">docs</a>'


def test_t42_only_http_and_https_links_are_links():
    cases = ["[a](http://x.test)", "[a](https://x.test)", "[a](ftp://x.test)", "[a](data:text/html,hi)", "[a](mailto:a@b.test)"]
    http, https, ftp, data, mail = render(*cases)
    assert "<a " in http and "<a " in https
    assert "<a " not in ftp and "<a " not in data and "<a " not in mail
