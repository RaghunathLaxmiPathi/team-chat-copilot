# Team Chat

A team chat service for about ten people: direct messages, group chats, channels, threads, mentions,
attachments, search, notifications, real-time delivery, and a built-in assistant called Copilot.
It runs on your machine with two commands and needs no database server, message broker, or container.

> This is a lab build, not production software. Section 6 lists every lab shortcut and what replaces it on Azure.

## 1. Run it

You need Python 3.12 or later. From this folder:

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m app
```

Open http://127.0.0.1:8000/ and sign in with one of these user names (no password in the lab):

| User name | Role |
| --- | --- |
| `alice`, `bob`, `carol` | Members |
| `admin1`, `admin2` | Administrators (they can add and deactivate users and create channels) |

Open a second browser tab and sign in as another user to chat between two people.

## 2. Use it

- **New** (left side) starts a direct message, a group chat, or (administrators) a channel.
- **Members** inside a group lets members add people. Administrators manage channel members.
- **Reply** opens a thread. Type `@name` to mention someone. Markdown is supported.
- **Attach** adds a file (up to 25 MB; png, jpg, gif, webp, pdf, txt, md, csv, docx, xlsx, pptx).
- The search box finds messages in the conversations you belong to.
- **Delete** removes your own message everywhere, including its files and search entries.
- If the connection drops, the page reconnects and catches up with nothing missed or duplicated.

## 3. Copilot

Copilot is a built-in assistant. Free-text questions and chat go to a **real language model**. By default that is a model
running on your own computer through Ollama, so chat text never leaves the machine. Commands such as `summarize`,
`search`, `my history`, and `weather in Paris` are answered by exact built-in code instead, so numbers and quotes
come from your real data and are not made up. If the model is not running, Copilot says so and falls back to
simple built-in answers.

### Set up the model (one time)

```
winget install Ollama.Ollama
ollama pull llama3.2:3b
```

Ollama keeps running in the background. Start the chat service as usual. To use a bigger or different model, set
`CHATAPP_AI_MODEL` (for example `qwen2.5:7b`, slower but stronger).

| Choice | Setting | Where your chat text goes |
| --- | --- | --- |
| A model on this computer (default) | `CHATAPP_AI_PROVIDER=ollama` | Nowhere. It stays on this machine. |
| Your Azure OpenAI resource | `CHATAPP_AI_PROVIDER=azure_openai`, `CHATAPP_AI_ENDPOINT=https://...`, `CHATAPP_AI_API_KEY=...`, `CHATAPP_AI_MODEL=<deployment name>` | **To that Azure resource.** Use only after a data-protection review. |
| No model | `CHATAPP_AI_PROVIDER=none` | Nowhere. Only the simple built-in answers. |

What the model is given: the system rules, the people in the conversation, and the last 20 messages of the
conversation it was asked in, limited to what the asker may see. In the asker's private chat, and only while their
"use my history" switch is on, it also gets their details and recent history. Messages from other people are labelled
as untrusted text and are never placed in the instructions. The model cannot take actions. It can only reply.

| Where | What it does |
| --- | --- |
| Your private chat with Copilot (every user has one) | Answers everything. Can use your own history and details. Only you can read it. |
| Every group chat and channel | Copilot joins automatically. It replies to everything you write while the top-bar switch "Copilot replies to everything I write" is on, and to `@copilot ...` otherwise. |
| Direct messages between two people | Copilot is not added: a direct message stays between those two people. |

Things to ask (in a group, start with `@copilot`):

- `summarize [number]`, `search <words>`, `actions`, `members`, `help`
- `time`, `time in Tokyo`, `weather in Seattle` (live data)
- `online` (who has the chat open right now, among people you share a chat with)
- `status` (live service health, administrators only)
- In the private chat only: `my details`, `my history [number]`, `my mentions`, `unread`, `my chats`, and `search <words>` across all your chats

Privacy rules the code enforces:

- It only reads history when asked, and only what the person asking may see.
- Your history and details are used only in your private chat, never in a group.
- The switch "Let Copilot use my history and details" turns that off.
- Chat text goes to a language model only through the setting above. With the default (a model on this computer) it never leaves the machine.
- Live weather and the time in unknown places are looked up on Open-Meteo. **Only the place name leaves the server**, never chat text or names. Turn it off with `CHATAPP_COPILOT_WEB=false`.
- To remove Copilot altogether: `CHATAPP_COPILOT=false`.

## 4. Configuration

Environment variables, all optional. See `app/config.py` for the full list.

| Variable | Default | Meaning |
| --- | --- | --- |
| `CHATAPP_DB_PATH` | `data/chatapp.db` | Database file |
| `CHATAPP_ATTACHMENT_DIR` | `data/attachments` | Attachment folder |
| `CHATAPP_PORT` / `CHATAPP_HOST` | `8000` / `127.0.0.1` | Where it listens |
| `CHATAPP_ADMIN_USERNAMES` | `admin1,admin2` | Administrators created at first start (at least two) |
| `CHATAPP_SEED_USERS` | `alice,bob,carol` | Sample members (lab only) |
| `CHATAPP_RETENTION_DAYS` | `0` (off) | Remove message content older than this many days |
| `CHATAPP_COPILOT` | `true` | Turn the assistant on or off |
| `CHATAPP_COPILOT_AUTO_DEFAULT` | `true` | New users get replies to everything they write |
| `CHATAPP_COPILOT_AUTO_JOIN` | `true` | Copilot joins every group chat and channel |
| `CHATAPP_COPILOT_PRIVATE_CHAT` | `true` | Every user gets a private chat with Copilot |
| `CHATAPP_COPILOT_WEB` | `true` | Allow live weather and time lookups |
| `CHATAPP_AI_PROVIDER` | `ollama` | `ollama` (local model), `azure_openai`, or `none` |
| `CHATAPP_AI_MODEL` | `llama3.2:3b` | Model name (or Azure deployment name) |
| `CHATAPP_AI_ENDPOINT` | `http://127.0.0.1:11434` | Where the model runs |
| `CHATAPP_AI_API_KEY` | none | Only for Azure OpenAI. Never log or commit it. |
| `CHATAPP_AI_TIMEOUT_S` | `120` | How long to wait for the model before using the simple answer |

## 5. Test it, check it, and operate it

```
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest -q
```

- `GET /healthz` (liveness) and `GET /readyz` (database check) need no sign-in.
- `GET /metrics` and `GET /api/v1/slo` (administrators) show live counts, the Success Rate, and delivery latency at
  P50, P75, P90, P95, and P99 for 1 hour, 24 hours, and 28 days.
- Every response has an `X-Request-ID` that matches the log line. Logs are JSON on standard output and never hold message text.
- Back up while running: `python -m app.backup <destination file>`.
- Runbook: if the page shows "Reconnecting", check `/readyz`; if the database is not ready, check disk space and
  file permissions on the `data` folder. Restart with `python -m app`. Clients resume without losing messages.

## 6. Lab shortcuts (not for production)

| Lab choice | Production replacement |
| --- | --- |
| Development sign-in with no password | Microsoft Entra ID with MFA |
| Plain HTTP on localhost | TLS at Azure Front Door or App Service |
| One process, one SQLite file, no replication | Zone-redundant Azure SQL or PostgreSQL, two or more instances |
| In-process real-time hub | Azure Web PubSub or Azure SignalR Service |
| Files on local disk, scanner accepts everything | Azure Blob Storage with Defender for Storage malware scanning |
| No encryption at rest | Service encryption with customer-managed keys in Key Vault |
| Metrics and objectives inside the service | OpenTelemetry to Azure Monitor, external availability probes |
| Email and push are queued, never sent | Azure Communication Services and Notification Hubs |
| Local model through Ollama (or none) | An approved model service in the organization's tenant, such as Azure OpenAI, after a data-protection review |

The full design, with requirements traceability, is in the documents in the folder above this one:
`chatapp.requirements.md`, `chatapp.funcspecs.md`, `chatapp.archspecs.md`, and `chatapp.testspecs.md`.
