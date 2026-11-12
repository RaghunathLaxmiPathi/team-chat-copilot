"""Builds the project site (docs/) from the markdown documents. Run: python tools/build_site.py

Needs the `markdown` package (pip install markdown). The pages load Mermaid from a CDN to draw the diagrams.
"""
import html
import re
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs"
REPO = "https://github.com/RaghunathLaxmiPathi/team-chat-copilot"

DOCS = [
    ("chatapp.assumptions", "Assumptions", "What we believe is true, how confident we are, and what could go wrong."),
    ("chatapp.assumptions.gao", "Assumptions critique", "Gaps found in the assumptions and how each was resolved."),
    ("chatapp.requirements", "Requirements", "What the service must do, with the Success Rate and Latency objectives."),
    ("chatapp.requirements.gao", "Requirements critique", "Findings on the requirements."),
    ("chatapp.funcspecs", "Functional specifications", "Use cases, rules, limits, and what users see."),
    ("chatapp.funcspecs.gao", "Functional specifications critique", "Findings on the functional specifications."),
    ("chatapp.archspecs", "Architecture specifications", "Stack, components, API, diagrams, Fundamentals, and risks."),
    ("chatapp.archspecs.gao", "Architecture critique", "Findings on the architecture."),
    ("chatapp.testspecs", "Test specifications", "What is tested, how, and what cannot be tested locally."),
    ("chatapp.testspecs.gao", "Test specifications critique", "Findings on the test specifications."),
    ("chatapp.implementation.gao", "Implementation critique", "Findings on the working application."),
]
TITLES = {name: title for name, title, _ in DOCS}

CSS = """
:root{--text:#111827;--muted:#4b5563;--accent:#1d4ed8;--border:#d1d5db;--panel:#f3f4f6}
*{box-sizing:border-box}body{margin:0;font:16px/1.6 system-ui,"Segoe UI",sans-serif;color:var(--text)}
a{color:var(--accent)}a:focus-visible,button:focus-visible{outline:3px solid #f59e0b;outline-offset:2px}
.skip{position:absolute;left:-999px}.skip:focus{left:8px;top:8px;background:#000;color:#fff;padding:6px 10px}
header.site{background:#0f172a;color:#fff;padding:12px 20px;display:flex;gap:20px;align-items:center;flex-wrap:wrap}
header.site a{color:#fff;text-decoration:none}header.site .brand{font-weight:700;font-size:1.1rem}
header.site nav a{margin-right:14px;opacity:.9}header.site nav a:hover{text-decoration:underline}
.layout{display:grid;grid-template-columns:260px 1fr;gap:24px;max-width:1280px;margin:0 auto;padding:20px}
aside.side{font-size:.92rem;position:sticky;top:12px;align-self:start}
aside.side h2{font-size:.85rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin:0 0 6px}
aside.side ul{list-style:none;margin:0 0 16px;padding:0}aside.side li a{display:block;padding:4px 8px;border-radius:6px;text-decoration:none}
aside.side li a[aria-current=page]{background:var(--panel);font-weight:700}
main{min-width:0}main h1{margin-top:0}
main table{border-collapse:collapse;display:block;overflow-x:auto;margin:12px 0}
main th,main td{border:1px solid var(--border);padding:6px 10px;vertical-align:top;font-size:.93rem}
main th{background:var(--panel);text-align:left}
main blockquote{margin:12px 0;padding:8px 16px;border-left:4px solid var(--accent);background:#eff6ff}
main code{background:var(--panel);padding:1px 5px;border-radius:4px;font-size:.9em}
main pre{background:#0f172a;color:#e5e7eb;padding:12px;border-radius:8px;overflow:auto}
main pre code{background:none;color:inherit;padding:0}
pre.mermaid{background:#fff;color:var(--text);border:1px solid var(--border);text-align:center}
.hero{background:linear-gradient(135deg,#0f172a,#1e3a8a);color:#fff;border-radius:14px;padding:32px;margin-bottom:24px}
.hero h1{color:#fff;font-size:2rem;margin:0 0 8px}.hero p{max-width:60ch;color:#dbeafe}
.hero a.btn{display:inline-block;background:#fff;color:#0f172a;padding:8px 16px;border-radius:8px;text-decoration:none;font-weight:600;margin:6px 8px 0 0}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px;margin:16px 0}
.card{border:1px solid var(--border);border-radius:10px;padding:14px 16px}.card h3{margin:0 0 6px;font-size:1.02rem}
.card p{margin:0;color:var(--muted);font-size:.93rem}
footer{max-width:1280px;margin:0 auto;padding:20px;color:var(--muted);font-size:.9rem;border-top:1px solid var(--border)}
@media(max-width:860px){.layout{grid-template-columns:1fr}aside.side{position:static}}
"""

MERMAID = """<script type="module">
import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs";
mermaid.initialize({startOnLoad:true,securityLevel:"strict",theme:"default"});
</script>"""


def sidebar(current: str) -> str:
    def item(href, label, cur):
        mark = ' aria-current="page"' if cur else ""
        return f'<li><a href="{href}"{mark}>{html.escape(label)}</a></li>'

    docs = "".join(item(f"{n}.html", t, n == current) for n, t, _ in DOCS)
    return (f'<aside class="side" aria-label="Documents"><h2>Project</h2><ul>{item("index.html", "Overview", current == "index")}</ul>'
            f"<h2>Design documents</h2><ul>{docs}</ul></aside>")


def page(title: str, body: str, current: str, mermaid_needed: bool) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} - Team Chat with Copilot</title><style>{CSS}</style></head>
<body><a class="skip" href="#content">Skip to content</a>
<header class="site"><a class="brand" href="index.html">Team Chat with Copilot</a>
<nav aria-label="Main"><a href="index.html">Overview</a><a href="chatapp.requirements.html">Requirements</a>
<a href="chatapp.archspecs.html">Architecture</a><a href="{REPO}">Source code</a></nav></header>
<div class="layout">{sidebar(current)}<main id="content">{body}</main></div>
<footer>Lab build, not production software. Generated from the markdown documents in the repository by tools/build_site.py.</footer>
{MERMAID if mermaid_needed else ""}</body></html>"""


def fix_links(body: str) -> str:
    # Links between documents become links between pages.
    body = re.sub(r'href="(?:\./)?(chatapp\.[a-z.]+?)\.md(#[^"]*)?"', lambda m: f'href="{m.group(1)}.html{m.group(2) or ""}"', body)
    # Links into the code go to the repository.
    body = re.sub(r'href="(?:\./)?chatapp/README\.md"', f'href="{REPO}/blob/main/chatapp/README.md"', body)
    body = re.sub(r'href="(?:\./)?chatapp/?"', f'href="{REPO}/tree/main/chatapp"', body)
    return body


def convert(text: str) -> tuple[str, bool]:
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "toc", "sane_lists"])
    has_mermaid = 'class="language-mermaid"' in body
    body = re.sub(r'<pre><code class="language-mermaid">(.*?)</code></pre>', r'<pre class="mermaid">\1</pre>', body, flags=re.S)
    return fix_links(body), has_mermaid


def landing() -> str:
    cards = "".join(
        f'<div class="card"><h3><a href="{n}.html">{html.escape(t)}</a></h3><p>{html.escape(d)}</p></div>'
        for n, t, d in DOCS if not n.endswith(".gao") or n == "chatapp.implementation.gao"
    )
    return f"""
<section class="hero"><h1>Team Chat with Copilot</h1>
<p>A team chat service for about ten people, designed from assumptions outward and documented at every step.
It includes direct messages, group chats, channels, threads, real-time delivery, and an AI assistant that runs on a
model on your own computer.</p>
<a class="btn" href="chatapp.requirements.html">Read the requirements</a>
<a class="btn" href="chatapp.archspecs.html">See the architecture</a>
<a class="btn" href="{REPO}">View the code</a></section>

<h2>What it does</h2>
<div class="cards">
<div class="card"><h3>Real-time team chat</h3><p>Direct messages, group chats, channels, threads, mentions, markdown, attachments, search, and notifications. Messages arrive instantly and in order, with nothing missed or duplicated after a dropped connection.</p></div>
<div class="card"><h3>Copilot, a real AI assistant</h3><p>Joins every group and channel, replies to everything you write when you let it, and answers from a language model running on your own computer. Your history and details are used only in your private chat.</p></div>
<div class="card"><h3>Live data</h3><p>The time in any place, live weather, who has the chat open, and live service health for administrators.</p></div>
<div class="card"><h3>Measured objectives</h3><p>Success Rate and delivery latency at P50, P75, P90, P95, and P99 over 1 hour, 24 hours, and 28 days, with minimum sample rules and a burn-rate warning.</p></div>
<div class="card"><h3>Privacy by design</h3><p>Server-side membership checks everywhere, deletion that reaches every copy, logs with no message text or tokens, and a data boundary around what the AI is given.</p></div>
<div class="card"><h3>Tested</h3><p>105 automated tests cover ordering, retries, permissions, deletion, real-time delivery, the objectives, privacy, and the assistant.</p></div>
</div>

<h2>Try it</h2>
<p>The chat needs its server, so it cannot run on this page. It runs on your own computer with two commands and needs
no database server, message broker, or container:</p>
<pre><code>cd chatapp
python -m venv .venv
.venv\\Scripts\\python -m pip install -r requirements.txt
.venv\\Scripts\\python -m app</code></pre>
<p>Then open <code>http://127.0.0.1:8000/</code> and sign in as <code>alice</code>, <code>bob</code>, <code>carol</code>,
<code>admin1</code>, or <code>admin2</code>. For the AI assistant, install Ollama and run <code>ollama pull llama3.2:3b</code> once.</p>

<h2>The documents</h2>
<p>Each document builds on the one before it, and each has a critique with findings that were fixed or deferred.</p>
<div class="cards">{cards}</div>
<p><strong>Honest limits.</strong> This is a lab build. It uses a development sign-in instead of Microsoft Entra ID, one
process and one SQLite file instead of a replicated store, and a small local model. The architecture document lists
every shortcut and its production replacement.</p>
"""


def main() -> None:
    OUT.mkdir(exist_ok=True)
    (OUT / ".nojekyll").write_text("")
    (OUT / "index.html").write_text(page("Overview", landing(), "index", False), encoding="utf-8")
    for name, title, _ in DOCS:
        source = ROOT / f"{name}.md"
        body, needs_mermaid = convert(source.read_text(encoding="utf-8"))
        (OUT / f"{name}.html").write_text(page(title, body, name, needs_mermaid), encoding="utf-8")
        print("built", name)
    print("built index")


if __name__ == "__main__":
    main()
