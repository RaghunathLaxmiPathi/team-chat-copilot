# Team Chat Application: Requirements

Date: 2026-11-11
Source: [chatapp.assumptions.md](./chatapp.assumptions.md)

> **Status at a glance**
> 66 requirements in sections 2 to 8. Each one traces to one or more assumptions (A-xx). The "Lab" column says how much is built in this lab: **Yes** (built), **Stub** (a simplified stand-in), or **No** (production only, not built).
> Chosen with the owner: Python stack, Success Rate SLO 99.9 percent, latency percentiles P50 200 ms, P75 400 ms, P90 700 ms, P95 1000 ms, P99 2000 ms, windows of 1 hour, 24 hours, and 28 days rolling.

## Contents

1. [Scope and conventions](#1-scope-and-conventions)
2. [Users and access](#2-users-and-access)
3. [Conversations and membership](#3-conversations-and-membership)
4. [Messaging](#4-messaging)
5. [Delivery and real-time behavior](#5-delivery-and-real-time-behavior)
6. [Service level objectives](#6-service-level-objectives)
7. [Quality, capacity, availability, and resiliency](#7-quality-capacity-availability-and-resiliency)
8. [Security, privacy, accessibility, and supportability](#8-security-privacy-accessibility-and-supportability)
9. [Out of scope](#9-out-of-scope)
10. [Assistant, added at the owner's request](#10-assistant-added-at-the-owners-request-after-the-first-review)
11. [Open items](#11-open-items)

---

## 1. Scope and conventions

- The product is a web-based chat service for the owner's direct team of about 10 people (A-01, A-02, A-09).
- "Must" means required. "Should" means expected unless there is a stated reason.
- Several values are proposed in the assumptions, not confirmed (Low confidence). Where a requirement depends on one, the Trace column names the assumption so it can be revisited when that assumption is confirmed.
- This lab builds a runnable version on a laptop. It is not a production Microsoft service. The Lab column and the risks section of the architecture document ([chatapp.archspecs.md](./chatapp.archspecs.md)) record every lab shortcut.

## 2. Users and access

| ID | Requirement | Trace | Lab |
| --- | --- | --- | --- |
| FR-01 | Users must sign in with their Entra ID corporate identity. The service must not store passwords. | A-03 | Stub: a development sign-in for existing users that issues a signed token. No Entra ID. |
| FR-02 | Only active, registered members of the team may use the service. A request from anyone else must be refused. | A-01, A-04 | Yes |
| FR-03 | There must be at least two administrators. Administrators can add users and deactivate users. | A-30 | Yes: two administrators are created at first start. |
| FR-04 | When a user is deactivated, their access must end immediately for all sessions, including open real-time connections. Their past messages stay. | A-19, A-30 | Yes |
| FR-05 | Messages from a deactivated user must show the author's name with the label "former member". | A-19 | Yes |
| FR-06 | In v1, all users belong to one organization. Authorization must be based on per-conversation membership so another team can be added later without a redesign. | A-04 | Yes |

## 3. Conversations and membership

| ID | Requirement | Trace | Lab |
| --- | --- | --- | --- |
| FR-10 | A user can start a direct message (1:1) with another user. There is at most one direct conversation per pair of users. Creating one that already exists returns the existing one. | A-06 | Yes |
| FR-11 | Any user can create a group chat and invite others. A group chat has at most 20 members. | A-06, A-30, A-31 | Yes |
| FR-12 | Administrators create channels and manage channel membership. A channel has at most 100 members. Channels have a unique name. | A-06, A-30, A-31 | Yes |
| FR-13 | Members of a group chat can add members. A member can leave a group chat or channel. Administrators can remove members from channels. | A-30 | Yes |
| FR-14 | Removing a member from a conversation must end their access to it immediately, including real-time delivery. | A-19, A-22 | Yes |
| FR-15 | A person added to a channel sees its full history. A person added to a group chat sees only messages sent after they joined. A person removed from a group chat and added again sees messages from their first join and after the re-add, but not those sent while they were removed. Direct messages have no joining. | A-31, A-22 | Yes |
| FR-16 | Direct messages must be readable only by their two participants. | A-22 | Yes |

## 4. Messaging

| ID | Requirement | Trace | Lab |
| --- | --- | --- | --- |
| FR-20 | A member can send a text message of 1 to 4,000 characters to a conversation they belong to. | A-07, A-31 | Yes |
| FR-21 | Messages can use markdown formatting. Plain text is valid markdown. The rendered result must be sanitized so no script can run. | A-07, A-23 | Yes |
| FR-22 | A member can reply to a message in the same conversation. Replies are grouped in a thread under the original message. | A-07 | Yes |
| FR-23 | A member can mention other members of the conversation with @username. A mentioned member must receive a notification. | A-07 | Yes |
| FR-24 | A member can attach files and images up to 25 MB each. Only allowed file types are accepted. Every attachment must be scanned for malware before others can open it. Access follows the conversation's membership. | A-23 | Yes for size, type, and access. Stub for malware scanning (a hook that accepts all files). |
| FR-25 | A member can search message text across the conversations they belong to. Search must never return results from conversations they do not belong to. | A-07, A-20 | Yes |
| FR-26 | A member receives in-app notifications for new messages in their conversations and for mentions. Email and push notifications must not contain message text. | A-07, A-20 | In-app: Yes. Email and push: Stub (a record of the notification only). |
| FR-27 | A user can delete a message they wrote. The message disappears from all users' views immediately. | A-15, A-17 | Yes |
| FR-28 | A deleted message must have its content removed from primary storage and the search index within 24 hours, and from backups when they expire (within 35 days). | A-17 | Yes in primary storage and search (immediately). Backups: No. |
| FR-29 | A deleted message that has replies is replaced in its thread by a "message deleted" placeholder. The replies stay. | A-17 | Yes |
| FR-30 | Message times must be stored in UTC and shown in each user's own time zone. | A-31 | Yes |

## 5. Delivery and real-time behavior

| ID | Requirement | Trace | Lab |
| --- | --- | --- | --- |
| FR-40 | Messages must be pushed to online recipients as they are sent, without the recipient asking. | A-10 | Yes |
| FR-41 | The server must assign the order of messages within a conversation. Every device must show the same order. | A-13 | Yes |
| FR-42 | Every message must carry a unique ID created by the sender. A retry with the same ID must never create a second message. | A-12, A-13 | Yes |
| FR-43 | A message must be shown as sent only after the server has stored it durably. | A-13, A-27 | Yes |
| FR-44 | The sender must see the status of each message (sending, sent, or failed). The client must retry automatically after a failure. | A-12 | Yes |
| FR-45 | A user who was offline or disconnected must receive every message they missed, in order, when they return. Missed messages load in pages of 50. | A-11, A-31 | Yes |
| FR-46 | A user can send at most 30 messages per minute. Beyond that, the service refuses with a clear "slow down" response. | A-31 | Yes |
| FR-47 | A user can mark a conversation read up to a message. The service tracks unread counts per conversation. | A-07, A-11 | Yes |

## 6. Service level objectives

These are the customer-centric SLOs. Each is measured over three windows: **1 hour**, **24 hours**, and **28 days rolling**.

| ID | Requirement | Trace |
| --- | --- | --- |
| SLO-01 | **Success Rate SLO.** At least 99.9 percent of valid customer requests must succeed in every window. A request counts as failed when the service returns a 5xx response or does not answer within 10 seconds. A failed real-time connection attempt, or a resume that returns an error, also counts as a failed request. A client error (4xx) is not a failure of the service and is excluded from the count. | A-26, A-33 |
| SLO-02 | **Latency SLO.** Message delivery latency is measured from the moment the server receives a message to the moment the recipient's client confirms receipt. Only recipients with an open real-time connection at send time are measured. Recipients who are offline are covered by catch-up (FR-45), not by this SLO. In every window, at least 50 percent of deliveries must arrive within 200 ms (P50), 75 percent within 400 ms (P75), 90 percent within 700 ms (P90), 95 percent within 1,000 ms (P95), and 99 percent within 2,000 ms (P99). | A-29 |
| SLO-03 | The service must expose the measured Success Rate and each latency percentile for each window, so the objectives can be checked at any time. | A-33 |
| SLO-04 | A burn-rate warning must be raised when the Success Rate in the 1-hour window falls below target while the 24-hour window is still within target, so the on-call person can act before the 28-day budget is spent. | A-33 |
| SLO-05 | A window must have a minimum number of samples before a value is reported: 100 samples for P99, 30 for P95 and below, and 30 requests for the Success Rate. Below that, the service must report "insufficient data" instead of a value, and must not raise a warning from it. | A-33, A-28 |

Notes:

- P95 at 1,000 ms is fixed by the owner's statement (A-29). The other percentiles and the success target windows are proposed and need confirmation (A-26 and A-29 are Low or Medium confidence).
- With about 2,000 messages a day (A-28), the 1-hour window holds roughly 100 requests. A single failure then breaks 99.9 percent in that window. The 1-hour window is therefore for fast warning, and the 28-day window is the one that defines compliance.

## 7. Quality, capacity, availability, and resiliency

| ID | Requirement | Trace | Lab |
| --- | --- | --- | --- |
| NFR-01 | Availability target: 99.9 percent per month for sending and receiving messages. A deployment must not lose messages. | A-26 | Partial: the service is single-instance, so the target is designed for but not met. |
| NFR-02 | An acknowledged message must survive a service restart. Recovery point objective is zero for acknowledged messages. | A-27, A-11 | Yes on one machine (durable write before acknowledgment). No replication. |
| NFR-03 | Recovery time objective is 4 hours for a full regional failure. Backups are taken at least daily, and a restore is tested at least every quarter. | A-27 | Stub: a backup command and a restore test. |
| NFR-04 | The service must run for the expected load: 10 users, about 2,000 messages a day (1 KB each), about 20 attachments a day (2 MB each), 10 concurrent connections. It should have 10 times headroom so growth does not force a rewrite. | A-28 | Yes |
| NFR-05 | The retention period must be configurable. No requirement may assume "keep forever". | A-16 | Yes: a setting and a purge job. Default is no purge until compliance rules are known. |
| NFR-06 | Before launch there must be automated tests for message ordering, duplicate prevention, reconnect and catch-up, permission checks, and accessibility checks. | A-14, A-13 | Yes, except full accessibility audit. |
| NFR-07 | On reconnect, catch-up must be bounded by paging, so a long absence does not overload the service or the client. | A-31 | Yes |
| NFR-08 | The service must run on Microsoft Azure, with separate development, test, and production environments. Production data must never be copied to development or test. | A-25 | No (runs locally) |

## 8. Security, privacy, accessibility, and supportability

### Security

| ID | Requirement | Trace | Lab |
| --- | --- | --- | --- |
| SEC-01 | All connections must use TLS. | A-22 | No: localhost over HTTP. |
| SEC-02 | Stored data, attachments, and backups must be encrypted at rest with managed keys. | A-22 | No |
| SEC-03 | Authorization must be checked on the server for every request and every real-time connection: a user can read a conversation only if they are a current member. | A-22, A-21 | Yes |
| SEC-04 | Administrators and operators must have no routine access to message content. The administration interface must not include a way to read messages. | A-22 | Yes |
| SEC-05 | Administrative actions and permission changes must be written to an audit log. | A-22 | Yes |
| SEC-06 | Sign-in must follow the organization's Entra ID policy, including multifactor authentication. | A-22, A-03 | No |
| SEC-07 | The data must be classified as Confidential and protected accordingly. | A-22 | Documented only |
| SEC-08 | Rendered content must be sanitized. Attachments must be limited by size and type and scanned. | A-23 | Yes except scanning (stub). |
| SEC-09 | A session must last at most 8 hours. The server must check on every request and every real-time connection that the user is still active, so deactivation takes effect immediately. | A-22, A-19, A-30 | Yes |

### Privacy

| ID | Requirement | Trace | Lab |
| --- | --- | --- | --- |
| PRV-01 | Deletion takes precedence over retention. | A-15, A-16 | Yes |
| PRV-02 | Deletion and retention must apply to every copy: the search index, notification records, replies, and attachments. | A-20 | Yes, except backups. |
| PRV-03 | Logs must never contain message text. | A-33, A-22 | Yes |
| PRV-04 | The service must follow Microsoft privacy and data-handling requirements. The specific compliance, residency, and data-subject-request rules are not yet known and must be confirmed before launch. | A-18 | Open item |

### Accessibility

| ID | Requirement | Trace | Lab |
| --- | --- | --- | --- |
| ACC-01 | The interface must meet WCAG 2.1 level AA and Microsoft accessibility requirements, and must be fully usable by keyboard. | A-24 | Yes by design, not formally audited. |
| ACC-02 | New messages must be announced to screen readers politely, without interrupting the user. | A-24 | Yes |
| ACC-03 | Threads, @mentions, message lists, and notifications must have accessible structure and labels. | A-24 | Yes |

### Supportability

| ID | Requirement | Trace | Lab |
| --- | --- | --- | --- |
| OPS-01 | The service must monitor health, delivery latency, delivery failures, error rate, connection counts, and storage growth. | A-33 | Yes: health checks, a metrics endpoint, and an SLO endpoint. |
| OPS-02 | The service must alert the on-call person when targets are at risk. | A-33 | Stub: warning state on the SLO endpoint. No alert routing. |
| OPS-03 | A named service owner, an on-call rotation, an incident path, and a runbook must exist before launch. | A-32 | Stub: a runbook in the README. |
| OPS-04 | Deployment and updates must be automated. | A-32 | No |
| OPS-05 | Every request must carry a correlation ID that appears in logs and in the response, so support can trace a failure. | A-33, A-32 | Yes |

## 9. Out of scope

- Voice (A-08).
- Native mobile and desktop clients (A-09).
- External guests and other teams in v1 (A-04).
- Typing indicators and online presence. The assumptions leave these undecided (finding G-19 deferred), so they are not built.
- Video, screen sharing, other bots, and integrations. The assumptions leave these unstated (G-20 deferred), so they are not built. The one exception is the built-in assistant in section 10, added at the owner's request.
- Editing messages. The owner did not select it.
- Read receipts. The owner did not select it.

## 10. Assistant (added at the owner's request after the first review)

The owner asked for an assistant ("Copilot") that replies in every chat, can use the person's history and details, and can use live data. These requirements record that decision. They trace to the owner's instruction, not to an assumption, and they change the privacy position, so they need the confirmation listed in section 11 and in [chatapp.implementation.gao.md](./chatapp.implementation.gao.md).

| ID | Requirement | Trace | Lab |
| --- | --- | --- | --- |
| ASST-01 | The assistant is a member account that cannot sign in and cannot be deactivated. It joins every group chat and channel. It does not join direct messages between two people. | Owner request, FR-10, FR-16 | Yes |
| ASST-02 | In a group or channel it replies to everything a person writes when that person has "reply to everything" on (default on, per person), and otherwise only when mentioned. In a direct message with the assistant it always replies. | Owner request | Yes |
| ASST-03 | Every person has a private direct message with the assistant. | Owner request | Yes |
| ASST-04 | The assistant reads history only when asked, and only what the person asking is allowed to see (FR-15). It never answers another assistant. | FR-15, A-22 | Yes |
| ASST-05 | The person's own history and details (their messages, mentions, unread, chats, profile) are used only in the private chat, never in a group, and only while the person's "use my history" switch is on. | Owner request, PRV-01, A-22 | Yes |
| ASST-06 | The assistant gives live data: the time in any place, weather, who has the chat open among people the asker shares a chat with, and service status (administrators only). | Owner request, OPS-01 | Yes |
| ASST-07 | Chat text, names, and conversation details must never leave the server. The only outside call is a place name to a weather and time service, and it can be switched off. | PRV-03, A-22, A-18 | Yes, with the switch |
| ASST-08 | Free text goes to a language model. By default the model runs on the same computer, so chat text does not leave it. A remote model (Azure OpenAI) is allowed only by explicit configuration and needs a data-protection review first. Exact commands (summaries, history, search, live data) are answered by code, not by the model. If the model is unavailable the assistant says so and uses simple built-in answers. | A-18, A-22 | Yes |
| ASST-09 | The assistant and its replies do not weaken the SLOs: replies are produced after the sender's request completes, and outside calls run off the main loop. | SLO-01, SLO-02 | Yes |



## 11. Open items

These could change the requirements. They are carried from the assumptions document.

| Item | Who answers | Affects |
| --- | --- | --- |
| Retention period and compliance rules | Requester, privacy contact | PRV-01, PRV-02, PRV-04, NFR-05 |
| Attachment retention | Owner | FR-24, FR-28 |
| Team accessibility needs | Owner | ACC-01 to ACC-03 |
| Guests or other teams | Requester | FR-06, SEC-03 |
| Hosting regions and compliance baseline | Requester, platform owner | NFR-08 |
| Confirmation of the proposed numbers (availability, latency percentiles, limits) | Owner | NFR-01 to NFR-04, SLO-01, SLO-02 |
| "Plain text only" and "markdown" both selected (G-18) | Owner | FR-21: treated as markdown including plain text |
| Whether the whole team agrees to the assistant joining every group, replying to everything by default, and using the outside weather and time service (section 11) | Owner, team, privacy contact | ASST-01, ASST-02, ASST-07 |
