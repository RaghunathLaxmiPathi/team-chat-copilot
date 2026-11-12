# Team Chat with Copilot

A team chat service for about ten people, built from assumptions outward and documented at every step.
It has direct messages, group chats, channels, threads, mentions, attachments, search, notifications, real-time
delivery, and **Copilot**, a built-in AI assistant that runs on a model on your own computer.

- **Project site and design documents (web pages):** https://raghunathlaxmipathi.github.io/team-chat-copilot/
- **The application and how to run it:** [chatapp/README.md](chatapp/README.md)

> This is a lab build, not production software. It runs locally with two commands and needs no database server,
> message broker, or container. The README lists every lab shortcut and what replaces it on Azure.

## Quick start

```
cd chatapp
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m app
```

Open http://127.0.0.1:8000/ and sign in as `alice`, `bob`, `carol`, `admin1` or `admin2` (no password in the lab).
For the AI assistant, install [Ollama](https://ollama.com) and run `ollama pull llama3.2:3b` once.

## The chain of documents

Each document builds on the one before it, and each has a critique (GAO) with findings and a disposition.

| Step | Document | Critique |
| --- | --- | --- |
| 1. Assumptions | [chatapp.assumptions.md](chatapp.assumptions.md) | [chatapp.assumptions.gao.md](chatapp.assumptions.gao.md) |
| 2. Requirements (with SLOs) | [chatapp.requirements.md](chatapp.requirements.md) | [chatapp.requirements.gao.md](chatapp.requirements.gao.md) |
| 3. Functional specifications | [chatapp.funcspecs.md](chatapp.funcspecs.md) | [chatapp.funcspecs.gao.md](chatapp.funcspecs.gao.md) |
| 4. Architecture specifications | [chatapp.archspecs.md](chatapp.archspecs.md) | [chatapp.archspecs.gao.md](chatapp.archspecs.gao.md) |
| 5. Test specifications | [chatapp.testspecs.md](chatapp.testspecs.md) | [chatapp.testspecs.gao.md](chatapp.testspecs.gao.md) |
| 6. Implementation | [chatapp/](chatapp) | [chatapp.implementation.gao.md](chatapp.implementation.gao.md) |

## Tests

```
cd chatapp
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest -q
```

## Rebuilding the project site

The site in `docs/` is generated from the markdown documents: `python tools/build_site.py`.
