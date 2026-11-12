# Team Chat Application: Test Specifications

Date: 2026-11-11
Sources: [chatapp.requirements.md](./chatapp.requirements.md), [chatapp.funcspecs.md](./chatapp.funcspecs.md), [chatapp.archspecs.md](./chatapp.archspecs.md)

> **Status at a glance**
> 71 automated test cases and 3 manual checks. Every test traces to a requirement. The automated tests run the real service in memory with a temporary database and need no other software. Requirements that cannot be tested in a local lab are listed in section 6 with the reason.

## Contents

1. [Approach and environment](#1-approach-and-environment)
2. [How to run](#2-how-to-run)
3. [Automated test cases](#3-automated-test-cases)
4. [Service level objective tests](#4-service-level-objective-tests)
5. [Manual checks](#5-manual-checks)
6. [Coverage and gaps](#6-coverage-and-gaps)

---

## 1. Approach and environment

- **Level:** tests call the real HTTP routes and the real WebSocket through FastAPI's test client. Each test gets a fresh service with a temporary database and attachment folder, so tests never depend on each other.
- **Time:** where the rules depend on time (session expiry, retention, windows), the test changes the settings or the clock the code reads. It does not wait.
- **Users:** a helper creates an administrator and members and returns signed-in clients, so each test reads as a story.
- **Negative paths first:** every rule that protects data (membership, deletion, deactivation) has a test that shows the refusal, not only the success.
- **Evidence:** a test passes only when the response and the stored data both match. For example, a deletion test checks the response, the stored row, the search index, and the file on disk.

## 2. How to run

From the `chatapp/` folder, after the setup in the README:

```
python -m pytest -q
```

The browser-rendering tests (T-40 to T-43) use Node.js, which is already installed on this machine. They are skipped automatically if Node.js is not available.

## 3. Automated test cases

Test files are in `chatapp/tests/`. The "File" column names the file that holds each case.

### 3.1 Sign-in, users, and administration

| ID | Title | Trace | Steps | Expected result | File |
| --- | --- | --- | --- | --- | --- |
| T-01 | Sign in and read own profile | FR-01 | Sign in as a seeded member. Call `/me` with the token. | 200 with a token and expiry. `/me` returns the same user. | test_auth_users.py |
| T-02 | Unknown and deactivated users cannot sign in, with the same answer | FR-02 | Sign in with an unknown name. Deactivate a user, then sign in as them. | Both give 401 with identical text. | test_auth_users.py |
| T-03 | Bad, missing, tampered, and expired tokens are refused | SEC-09 | Call `/me` with no token, a random token, a token with one changed character, and a token with a past expiry. | 401 `unauthorized` each time. | test_auth_users.py |
| T-04 | Administrators create users, and others cannot | FR-03, SEC-05 | As administrator create a user. As a member try the same. Create a duplicate. Create with a bad name. | 201, then 403, 409, and 400. | test_auth_users.py |
| T-05 | At least two administrators always remain | FR-03 | Demote one of two administrators. Deactivate one of two. | Both refused with 409. With three administrators, one change succeeds. | test_auth_users.py |
| T-06 | Deactivation takes effect at once | FR-04, SEC-09 | Sign in a member, join a group chat and a direct message, then deactivate them. Use the old token. | The old token gives 401 on the next call. They are out of the group chat. The direct message remains for the other person. | test_auth_users.py |
| T-07 | Deactivated authors show as former members | FR-05 | Deactivate an author, then read their old messages as another member. | Messages remain. `sender_status` is `deactivated`. | test_auth_users.py |
| T-08 | A member cannot deactivate or change roles | SEC-03 | As a member call deactivate and role change. | 403 for both. | test_auth_users.py |
| T-09 | Start-up creates at least two administrators and refuses fewer | FR-03 | Start the service with one configured administrator. | The service refuses to start. With two it starts. | test_auth_users.py |

### 3.2 Conversations and membership

| ID | Title | Trace | Steps | Expected result | File |
| --- | --- | --- | --- | --- | --- |
| T-10 | Direct message is one per pair | FR-10 | Start a direct message A to B. Start it again from B to A. Start one with yourself or an unknown user. | First 201. Repeat 200 with the same conversation. Others 400. | test_conversations.py |
| T-11 | Group chat rules and limits | FR-11, FR-13 | Create with 0 others (fail), 1 other, 19 others. Add a 20th member. Add a 21st. | Fails with 400, then 201, 201, 200, 409. | test_conversations.py |
| T-12 | Concurrent sends get unique, gap-free numbers | FR-41, D-01 | From several members send 100 messages at once. Read them back. | Numbers run 1 to 100 with no gaps and no repeats. | test_messages.py |
| T-13 | Channel rules | FR-12 | A member tries to create a channel. An administrator creates one. Reuse the name in a different case. Add up to 100 members. | 403, then 201, then 409. The 101st member is refused with 409. | test_conversations.py |
| T-14 | Non-members and missing conversations look the same | FR-16, SEC-03 | A non-member requests a conversation, its messages, its thread, an attachment, and its search results. Request an unknown ID. | Every case gives 404 with the same body shape. Search returns nothing from it. | test_conversations.py |
| T-15 | Removal stops access at once | FR-14 | Remove a member from a group. They request the conversation and messages. | 404. The real-time channel stops delivering for it (see T-55). | test_conversations.py |
| T-16 | History visibility for group and channel members | FR-15 | In a group, send messages, then add a new member and send more. Remove and re-add them, with messages in between. In a channel do the same. | A group member sees from their first join, minus the gap. A channel member sees everything. | test_conversations.py |
| T-17 | Direct messages with a deactivated person | FR-04, A-19 | Deactivate B. A reads the direct message and tries to send. | A can read. Sending gives 409 `conversation_closed`. | test_conversations.py |
| T-18 | Leaving and role rules for members | FR-13 | A member leaves a group. A member tries to remove another from a channel. An administrator does. | Leave 204. Remove by member 403. By administrator 204. Direct message leave 400. | test_conversations.py |

### 3.3 Messages

| ID | Title | Trace | Steps | Expected result | File |
| --- | --- | --- | --- | --- | --- |
| T-20 | Send and validate | FR-20 | Send valid text, empty text, whitespace only, and 4,001 characters. Send exactly 4,000. | 201 for valid and 4,000. 400 for the others. Text is stored as typed. | test_messages.py |
| T-21 | Retry is idempotent | FR-42 | Send with a client ID twice. Send the same ID to a different conversation. | Second returns 200 with `duplicate` true and the same message. One row only. Other conversation gets 409. | test_messages.py |
| T-22 | An acknowledged message survives a restart | FR-43, NFR-02 | Send a message. Discard the service and start a new one on the same files. | The message is there with the same number. | test_messages.py |
| T-23 | Threads | FR-22 | Reply to a message. Reply to the reply. Reply to a message in another conversation. Fetch the thread. | Replies point to the original. Cross-conversation reply 400. The thread shows root and replies in order. | test_messages.py |
| T-24 | Mentions and notifications | FR-23, FR-26 | Mention a member, a non-member, and an unknown name. Read notifications. | Only the member gets a `mention` notification. The notification has no message text. | test_search_notifications.py |
| T-25 | Rate limit | FR-46 | Send 30 messages in a minute, then a 31st. | The 31st gives 429 with `Retry-After`. Another user is not affected. | test_messages.py |
| T-26 | Delete own message | FR-27, FR-28, FR-29, PRV-01, PRV-02 | Send a message with an attachment and a mention. Delete it. Have replies in place. | 204. The message reads as deleted with no text. Search does not find it. The file is gone from disk. The mention is removed. Replies remain. | test_messages.py |
| T-27 | Only the author can delete | FR-27 | Another member and an administrator try to delete. The author deletes twice. | 403 for both. 204 each time for the author. | test_messages.py |
| T-28 | Paging: before, after, around | FR-45, NFR-07 | Create 120 messages. Request the newest page, before a number, after a number, and around a number. Combine two cursors. | Pages hold at most 50 in ascending order. Flags are correct. Around gives up to 25 on each side. Two cursors give 400. | test_messages.py |
| T-29 | Unread counts and read position | FR-47 | Send messages from B to A. Check A's list. Mark read. Try to move backward. | Unread rises, then drops to zero. The position never moves back. | test_messages.py |

### 3.4 Attachments

| ID | Title | Trace | Steps | Expected result | File |
| --- | --- | --- | --- | --- | --- |
| T-30 | Upload, send, and download | FR-24 | Upload a small PDF. Send it in a message. Download as a member. | 201, then the message lists it, then the bytes match. Download is an attachment with `nosniff`. | test_attachments.py |
| T-31 | Size and type limits | FR-24, SEC-08 | Upload a file above the limit (limit lowered for the test) and a `.exe`. Upload a file named with path parts. | 413 and 415. The stored name is generated, never the user's name. | test_attachments.py |
| T-32 | Only members can upload or open | FR-24, SEC-03 | A non-member uploads to the conversation and downloads an attachment. | 404 for both. | test_attachments.py |
| T-33 | Attachment attach rules | FR-24 | Send with 6 attachments. Send using another person's upload. Send using an upload from another conversation. Reuse an already sent upload. | 400 in every case. | test_attachments.py |
| T-34 | Unsent uploads are removed after an hour | FR-24 | Upload but do not send. Advance the clock by an hour and run the cleanup. | The file and row are gone. | test_attachments.py |
| T-35 | The scanner can reject a file | FR-24, SEC-08 | Use a scanner that rejects one file. | The upload is refused with 400 and nothing is stored on disk or in the database. | test_attachments.py |

### 3.5 Search and notifications

| ID | Title | Trace | Steps | Expected result | File |
| --- | --- | --- | --- | --- | --- |
| T-36 | Search is limited to what the user may see | FR-25, PRV-02 | Send matching text in a shared conversation, a private one, a group before the user joined, and a deleted message. Search as the user. | Only the shared and post-join messages appear. | test_search_notifications.py |
| T-37 | Search input is safe | FR-25 | Search with quotes, `*`, `AND`, `OR`, `NEAR`, a one-character query, and 101 characters. | No error from the search engine. 400 for bad length. Words are matched as plain words. | test_search_notifications.py |
| T-38 | Notification list and read | FR-26 | List, mark one read, mark another person's notification. | Count falls. The other person's gives 404. | test_search_notifications.py |
| T-39 | Added-to-conversation notification | FR-26 | Add a member to a group. | They get an `added` notification and, when offline, an outbox entry with no message text. | test_search_notifications.py |

### 3.6 Message rendering and browser safety

| ID | Title | Trace | Steps | Expected result | File |
| --- | --- | --- | --- | --- | --- |
| T-40 | Hostile input is neutralized | FR-21, SEC-08, D-05 | Render script tags, `onerror` attributes, `javascript:` links, nested markup, and broken markdown. | No output contains a live tag from the input, an event attribute, or a `javascript:` link. | test_client_render.py |
| T-41 | Supported formatting works | FR-21 | Render bold, italic, inline code, a code block, a link, line breaks, and mentions. | The expected safe HTML for each. Plain text is unchanged apart from escaping. | test_client_render.py |
| T-42 | Only http and https links are links | FR-21 | Render links with `http`, `https`, `ftp`, `data`, and `mailto`. | Only `http` and `https` become links, and they carry `rel="noopener noreferrer"` and `target="_blank"`. | test_client_render.py |
| T-43 | Security headers are present | SEC-08, DD-10 | Request the page and an API response. | A content security policy, `nosniff`, `no-referrer`, and `frame-ancestors 'none'` are present. | test_slo_ops.py |

### 3.7 Real-time delivery

| ID | Title | Trace | Steps | Expected result | File |
| --- | --- | --- | --- | --- | --- |
| T-50 | Connect rules | FR-40, SEC-09 | Connect with a valid token, an invalid token, and a deactivated user's token. | `hello` for the valid one. Close 4401 for invalid. Close 4403 for deactivated. | test_realtime.py |
| T-51 | New messages are pushed | FR-40 | Two members connect. One sends. A non-member is also connected. | The other member gets the message frame. The non-member gets nothing. | test_realtime.py |
| T-52 | The sender's other devices get the message | FR-40, UC-07 | The sender has two connections. | Both receive the message. | test_realtime.py |
| T-53 | Order is the same for everyone | FR-41 | Two senders send alternately. Two receivers collect. | Both receivers see the same order, with ascending numbers. | test_realtime.py |
| T-54 | Resume replays what was missed, in order, in pages | FR-45, NFR-07 | A member is offline while 120 messages are sent. They connect and resume with their old position. | Two `resume_page` frames of at most 50 (the first with `has_more`), then `resume_done`. No gaps, no repeats. | test_realtime.py |
| T-55 | Resume reports deletions made while offline | FR-27, DD-12 | A member goes offline. Another deletes a message the first holds. The first resumes with its last sync time. | `resume_done` lists the deleted message. | test_realtime.py |
| T-56 | Deactivation closes live connections | FR-04 | Deactivate a connected user. | The connection closes with 4403 and later connects fail. | test_realtime.py |
| T-57 | Removal stops delivery | FR-14 | Remove a connected member from a group. Send a message. | They get `conversation_removed` and then nothing more for it. | test_realtime.py |
| T-58 | Slow client queue overflow | NFR-07, DD-01 | Use a connection with a tiny queue that never reads. Publish more events than fit. | That connection closes with 4408. Other connections are unaffected. | test_realtime.py |
| T-59 | Expired sessions are closed | SEC-09 | Connect with a token that expires soon. Run the sweeper after it expires. | The connection closes with 4401. | test_realtime.py |

## 4. Service level objective tests

### 4.1 Measurement logic (unit tests)

| ID | Title | Trace | Steps | Expected result | File |
| --- | --- | --- | --- | --- | --- |
| T-60 | Latency under the targets | SLO-02, NFR-04 | Connect a recipient who acknowledges every message. Send 500 messages one after another. Read the objectives report. | The 1-hour window shows samples and P50, P75, P90, P95, and P99 at or below 200, 400, 700, 1,000, and 2,000 ms. The measured values are printed. This is a local test: it checks the service part only, not the network. | test_slo_ops.py |
| T-61 | Success Rate counting | SLO-01 | Record successes, 4xx responses, 5xx responses, and a request over 10 seconds. | 4xx are not counted. 5xx and slow requests are failures. Rate is correct. | test_slo_ops.py |
| T-62 | Percentiles come from the right buckets | SLO-02 | Feed known latencies into the tracker. | Each percentile equals the upper edge of the bucket where its share is reached. | test_slo_ops.py |
| T-63 | Windows are separate | SLO-01, SLO-02 | Record events at several ages (30 minutes, 5 hours, 10 days). | The 1-hour, 24-hour, and 28-day windows each include exactly the events inside them. | test_slo_ops.py |
| T-64 | Too few samples report "insufficient data" | SLO-05 | Record 29 requests, then 30. Record 99 latency samples, then 100. | Status is `insufficient_data` below the minimum and a value at or above it. No warning is raised from insufficient data. | test_slo_ops.py |
| T-65 | Burn-rate warning | SLO-04 | Make the 1-hour rate fall below 99.9 percent while the 24-hour rate stays within target. | `burn_rate_warning` is true. It is false when both are within target or both are out. | test_slo_ops.py |
| T-66 | Counts survive a restart | SLO-03, DD-15 | Record events, save, create a new tracker on the same database. | The new tracker reports the same window values. | test_slo_ops.py |
| T-67 | Unconfirmed deliveries count as slow | SLO-02, DD-13 | Deliver to a recipient that never acknowledges. Run the sweeper after 10 seconds. | A sample is recorded in the slowest bucket. | test_slo_ops.py |
| T-68 | Operational routes are excluded and protected | OPS-01, F-06 | Call health, readiness, metrics, and objectives as a member and as an administrator. | Health and readiness are open. Metrics and objectives give 403 to a member. None of these change the request counts. | test_slo_ops.py |
| T-69 | Headroom: ten times the expected connections | NFR-04, A-28 | Register 100 connections (ten times the expected 10) on one channel. Publish 200 messages. Every connection acknowledges. | Every connection receives all 200 messages in order. No connection is closed. The measured latencies stay within the targets. | test_slo_ops.py |

### 4.2 Operations and privacy

| ID | Title | Trace | Steps | Expected result | File |
| --- | --- | --- | --- | --- | --- |
| T-70 | Error shape and correlation ID | OPS-05, DD-20 | Trigger a 400, 401, 403, 404, 409, and an internal error. Send a request with a good `X-Request-ID` and one with a bad one. | Every error has `code`, `message`, and `request_id` that matches the response header. A bad ID is replaced. The internal error leaks nothing. | test_slo_ops.py |
| T-71 | Logs hold no message text or tokens | PRV-03, DD-21, R-12 | Send a message with a unique marker and an attachment with a marker in its name. Connect a real-time client with a token in the address. Capture all logs. | None of the markers and no token appears in any log line, including the access lines for the real-time address. | test_privacy_retention.py |
| T-72 | Audit records | SEC-05, DD-19 | Create and deactivate a user. Add and remove members. Create a channel. | One audit row per action with actor, target, and time, and no message content. | test_privacy_retention.py |
| T-73 | No endpoint gives administrators message content | SEC-04, DD-09 | List every route. For each administrator-only route read its documented response. Call metrics. | No administrator-only route returns message text. | test_privacy_retention.py |
| T-74 | Retention removes old content, and is off by default | NFR-05, PRV-01 | With retention off, run the job. Then turn on a 30-day period and age some messages. | Nothing changes when off. When on, old content, files, and index entries are removed and newer ones stay. | test_privacy_retention.py |
| T-75 | Backup and restore | NFR-03 | Run the backup while messages are being sent. Open the copy. | The copy opens and holds a consistent set of messages. | test_privacy_retention.py |
| T-76 | Notifications hold no message text | PRV-04, A-20 | Send a mention with a unique marker. Read notifications and the outbox rows. | The marker appears in neither. | test_privacy_retention.py |
| T-77 | A failed send leaves nothing behind | FR-43, DD-03 | Make a step inside the send transaction fail (for example the notification step). Send. | An error response. No message row, no mention, no attachment link, and the next send gets the next unused number with no gap. | test_messages.py |
| T-78 | Times are stored in UTC | FR-30 | Create messages, notifications, and users. Read the stored times and the API times. | Every time is ISO 8601 in UTC and ends in `Z`. | test_messages.py |

## 5. Manual checks

| ID | Title | Trace | Steps | Expected result |
| --- | --- | --- | --- | --- |
| M-01 | Keyboard and screen reader check | ACC-01 to ACC-03 | Use the page with the keyboard only. Turn on a screen reader. Send and receive messages, open the thread, search, and open notifications. | Every control is reachable and operable. New messages are announced politely. Focus moves as described in the functional specs, section 9. |
| M-02 | Two-browser walk-through | FR-10 to FR-27, FR-40 | Sign in as two users in two windows. Start a direct message, send, receive, reply, mention, attach, delete, search. Stop the service for a few seconds and start it again. | The flows work as specified, and the page reconnects and catches up with no duplicates. |
| M-03 | Contrast and zoom check | ACC-01 | Check colors with an accessibility tool. Zoom to 200 percent. | AA contrast. No content lost or overlapping. |

## 6. Coverage and gaps

### Coverage by requirement

| Requirement group | Tests |
| --- | --- |
| FR-01 to FR-06 (users, access) | T-01 to T-09 |
| FR-10 to FR-16 (conversations) | T-10 to T-18 |
| FR-20 to FR-30 (messaging) | T-20 to T-29, T-30 to T-39, T-40 to T-42, T-78 |
| FR-40 to FR-47 (delivery) | T-21, T-22, T-25, T-28, T-29, T-50 to T-59, T-77 |
| SLO-01 to SLO-05 | T-60 to T-68 |
| NFR-02, NFR-03, NFR-04, NFR-05, NFR-06, NFR-07 | T-22, T-75, T-60 and T-69, T-74, this suite, T-28, T-54, T-58 |
| SEC-03 to SEC-05, SEC-08, SEC-09 | T-03, T-14, T-32, T-72, T-73, T-31, T-40 to T-43, T-59 |
| PRV-01 to PRV-04 | T-26, T-36, T-71, T-74, T-76 |
| OPS-01, OPS-05 | T-62 to T-70 |
| ACC-01 to ACC-03 | M-01, M-03 |

### Not tested in the lab, with the reason

| Requirement | Reason | How it would be tested in production |
| --- | --- | --- |
| FR-01 (real Entra ID), SEC-06 | No Entra ID in the lab | Integration tests against a test tenant, and conditional access checks |
| SEC-01, SEC-02 | No TLS or encryption at rest in the lab | Platform configuration checks and a scan for plain-text endpoints |
| SEC-07 | Classification is a document, not behavior | Review |
| NFR-01 (99.9 percent availability) | Needs weeks of operation on several instances | The 28-day Success Rate and external availability probes |
| NFR-08, OPS-04 | Hosting and deployment automation are not in the lab | Deployment pipeline tests per environment |
| OPS-02, OPS-03 | Alert routing, on-call, and ownership are organizational | Alert drill and runbook review before launch |
| FR-24 malware scanning (real) | The scanner is a stub | Test with the standard antivirus test file against the real scanner |
| FR-28 (backups) | No backup retention in the lab | Backup expiry check after 35 days |
| Latency over a real network | The local test removes the network | Synthetic client probes and client telemetry |
| Full accessibility audit | A formal audit needs specialist tools and users | Accessibility Insights in the build plus manual testing with assistive technology |
