# Team Chat Application: Functional Specifications

Date: 2026-11-11
Sources: [chatapp.requirements.md](./chatapp.requirements.md), [chatapp.assumptions.md](./chatapp.assumptions.md)

> **Status at a glance**
> 22 use cases, one web interface, one real-time channel. Every use case lists the requirements it satisfies. Behavior here is what a user or a tester can observe. How it is built is in [chatapp.archspecs.md](./chatapp.archspecs.md).

## Contents

1. [Roles](#1-roles)
2. [The interface](#2-the-interface)
3. [Use cases](#3-use-cases)
4. [Message states](#4-message-states)
5. [Rules, limits, and validation](#5-rules-limits-and-validation)
6. [Message formatting](#6-message-formatting)
7. [Notifications](#7-notifications)
8. [Errors the user can see](#8-errors-the-user-can-see)
9. [Accessibility behavior](#9-accessibility-behavior)
10. [Not specified](#10-not-specified)

---

## 1. Roles

| Role | Who | Can do |
| --- | --- | --- |
| Member | Any active team member | Chat in conversations they belong to, create direct and group chats, add members to groups they belong to, delete their own messages, search, attach files |
| Administrator | At least two people (FR-03) | Everything a member can do, plus: create channels, add and remove channel members, add users, deactivate users |

An administrator has no extra power to read other people's conversations (SEC-04). An administrator who is not a member of a channel cannot read it.

## 2. The interface

One web page with these areas.

| Area | What it shows | Trace |
| --- | --- | --- |
| Sign-in | A field for the user name and a Sign in button. Lab only: stands in for Entra ID. | FR-01 |
| Conversation list | Direct messages, group chats, and channels the user belongs to, each with an unread count. A "New" menu starts a direct message or group chat. Administrators also see "New channel". | FR-10 to FR-12, FR-47 |
| Conversation header | Name, member count, a Members button, and a Leave button for groups and channels. | FR-13 |
| Message list | Messages in order, with sender, time (in the user's time zone), and status for the user's own messages. A "Load earlier messages" button loads the previous 50. | FR-30, FR-44, FR-45 |
| Composer | A text box, an Attach button, and a Send button. Enter sends. Shift+Enter adds a new line. | FR-20, FR-24 |
| Thread panel | The original message and its replies, with a reply composer. | FR-22 |
| Search | A search box above the conversation list, with a result list. | FR-25 |
| Notifications | A bell button with a count, opening a list of mentions and invitations. | FR-26 |
| Administration | Visible to administrators only: add user, deactivate user. | FR-03, FR-04 |
| Connection banner | Shows "Reconnecting" when the real-time connection drops. | FR-40, FR-45 |

## 3. Use cases

### UC-01: Sign in (lab)

- **Trace:** FR-01, FR-02, SEC-09
- **Steps:** The user enters a user name and chooses Sign in. The service checks that the user exists and is active, then issues a session that lasts 8 hours. The page opens the real-time connection.
- **Result:** The conversation list appears.
- **Failures:** Unknown or deactivated user: "Sign-in failed" (the message does not say which). Production replaces this with Entra ID sign-in and the organization's policy.

### UC-02: Start a direct message

- **Trace:** FR-10, FR-16
- **Steps:** The user picks "New", then "Direct message", then a person. If a direct conversation with that person exists, it opens. Otherwise a new one is created with the two people.
- **Failures:** The person is not an active user.

### UC-03: Create a group chat

- **Trace:** FR-11, FR-13
- **Steps:** The user picks "New", then "Group chat", enters a name and chooses members. The creator is a member. Each added person gets an "added to conversation" notification.
- **Rules:** At most 20 members including the creator. At least 1 other person.

### UC-04: Create a channel (administrator)

- **Trace:** FR-12
- **Steps:** An administrator picks "New channel", enters a unique name (up to 50 characters), and chooses members. Members get an "added" notification.
- **Rules:** At most 100 members. Channel names are unique, ignoring case.
- **Failures:** Name already used: "A channel with that name already exists." A non-administrator gets "Not allowed."

### UC-05: Add or remove members

- **Trace:** FR-13, FR-14, FR-15
- **Steps:** In a group chat, any member can add members. In a channel, only an administrator can add or remove members. Any user can leave a group chat or channel. A direct message cannot change members.
- **Result:** An added person sees the conversation in their list. A removed person loses the conversation immediately: it leaves their list, their open real-time connection stops receiving it, and requests for it are refused.
- **Direct messages:** A direct message always keeps its two members. If one of them is deactivated (UC-17), the other keeps the history and sees "Name (former member)", and new messages to that conversation are refused with "This person is no longer a member."
- **Visibility:** A person added to a channel sees all history. A person added to a group chat sees messages sent from their first join onward, except any sent while they were removed.

### UC-06: Send a message

- **Trace:** FR-20, FR-41, FR-42, FR-43, FR-44, FR-46
- **Steps:** The user types text and presses Enter. The message appears at once in the list with status "Sending". The client sends it with a unique ID. When the service confirms it is stored, the status becomes "Sent" and the message takes its place in the confirmed order.
- **Failures:** If sending fails (network error or a server error), the status becomes "Failed to send, retrying" and the client retries with the same ID, with increasing waits up to 5 attempts. If all attempts fail, the status shows "Not sent" with a Retry button. A retry never creates a second message.
- **Too fast:** More than 30 messages in a minute: the message is not sent and the user sees "You are sending too fast. Try again in a few seconds." The message stays in the box.
- **Validation:** Empty or blank text is not sent. More than 4,000 characters shows "Message is too long (limit 4,000 characters)."

### UC-07: Receive a message in real time

- **Trace:** FR-40, FR-41, SLO-02, ACC-02
- **Steps:** When another member sends a message, the page receives it over the real-time connection and adds it to the open conversation in order. For a conversation that is not open, its unread count goes up. The page confirms receipt to the service.
- **Result:** Screen readers hear a polite announcement ("New message from Name") without moving focus.
- **Several devices:** A user can be signed in on several devices or tabs at once. Each one receives every message, including the user's own messages sent from another device, in the same order. Read state belongs to the user, not to a device.

### UC-08: Catch up after being offline

- **Trace:** FR-45, NFR-07
- **Steps:** When the page reconnects, it tells the service the last message number it has for each conversation and the server time of its last successful sync. The service replays missed messages in order, up to 50 per conversation at a time, and says whether more remain. It also returns the IDs of messages deleted since that sync time, and the page removes them from the screen. The page keeps requesting until it has everything.
- **Result:** No gaps and no duplicates, and no deleted message stays on screen. The "Reconnecting" banner clears.

### UC-09: Reply in a thread

- **Trace:** FR-22
- **Steps:** The user opens "Reply" on a message. The thread panel shows the original and its replies. The reply is sent like any message with a reference to the original. Replies also appear in the main message list, marked "Replying to Name".
- **Rules:** A reply must be in the same conversation as the original. Replying to a reply attaches to the same original.

### UC-10: Mention a member

- **Trace:** FR-23
- **Steps:** The user types @ and a user name. The text is shown highlighted. When sent, each mentioned person who is a member of the conversation gets a mention notification.
- **Rules:** Mentions of people who are not members, or of unknown names, are shown as plain text and send no notification. Up to 20 mentions are processed per message.

### UC-11: Attach a file

- **Trace:** FR-24, SEC-08
- **Steps:** The user chooses Attach and picks a file. The file uploads to the conversation. When the upload finishes it appears as a chip below the box with a Remove button. The user can add up to 5 files and send the message. Recipients see file name and size, and can open the file.
- **Rules:** Up to 25 MB per file. Allowed types: png, jpg, jpeg, gif, webp, pdf, txt, md, csv, docx, xlsx, pptx. Anything else is refused. Every file is scanned before it can be opened (lab: the scan accepts all files). Only members of the conversation can open a file. A file that is never sent with a message is removed after 1 hour.
- **Failures:** Too large: "File is larger than 25 MB." Wrong type: "This file type is not allowed."

### UC-12: Delete my message

- **Trace:** FR-27, FR-28, FR-29, PRV-01, PRV-02
- **Steps:** The user opens the menu on one of their own messages and chooses Delete, then confirms. The message turns into "Message deleted" for everyone at once. Replies stay under the placeholder. The message text and any attachments are removed from storage and from search.
- **Rules:** Only the author can delete. There is no undo.

### UC-13: Search

- **Trace:** FR-25, PRV-02
- **Steps:** The user types at least 2 characters and presses Enter. The page lists up to 50 matching messages, newest first, each with the conversation name, sender, time, and a text excerpt. Choosing a result opens that conversation at that message.
- **Rules:** Only conversations the user belongs to are searched, and only the part of history the user may see (UC-05). Deleted messages never appear. A group member sees only messages from their join point onward.
- **Opening a result:** The page loads the 25 messages before and the 25 after the matching message, with "Load earlier messages" and "Load later messages" buttons. This stays within the user's visible history.

### UC-14: Mark a conversation read

- **Trace:** FR-47
- **Steps:** Opening a conversation, or scrolling to the newest message, marks it read up to the newest visible message. The unread count resets to zero.

### UC-15: See notifications

- **Trace:** FR-26
- **Steps:** The bell shows the number of unread notifications. Opening it lists mentions and "added to conversation" items, newest first. Choosing one opens the conversation and marks the item read.
- **Rules:** See section 7.

### UC-16: Add a user (administrator)

- **Trace:** FR-03, SEC-05
- **Steps:** An administrator enters a user name and a display name. The user is created and can sign in. The action is written to the audit log.
- **Rules:** User names are 3 to 32 characters: lowercase letters, digits, dot, dash, and underscore. An administrator can also grant or remove the administrator role for another user. Any change that would leave fewer than two active administrators is refused.

### UC-17: Deactivate a user (administrator)

- **Trace:** FR-04, FR-05, FR-14, SEC-05, SEC-09
- **Steps:** An administrator chooses Deactivate for a user and confirms. The user's open real-time connections are closed at once. Every later request from that user is refused. The user is removed from all conversations. Their messages stay and show "Name (former member)". The action is written to the audit log.
- **Rules:** An administrator cannot deactivate themselves. A deactivation that would leave fewer than two active administrators is refused (FR-03).

### UC-18: Check service health and objectives (operator)

- **Trace:** OPS-01, SLO-03, SLO-04, SLO-05
- **Steps:** An operator opens the health and objectives pages. The basic health check needs no sign-in, so the platform can probe it. The objectives and metrics pages are limited to administrators. The objectives page shows, for the 1-hour, 24-hour, and 28-day windows, the Success Rate and the latency at P50, P75, P90, P95, and P99, with each compared to its target. A window with too few samples shows "insufficient data".

### UC-19: Reconnect after a dropped connection

- **Trace:** FR-40, FR-45
- **Steps:** When the real-time connection drops, the banner shows "Reconnecting". The page retries with increasing waits, up to 30 seconds apart. On success it runs the catch-up in UC-08.

### UC-20: Sign out

- **Trace:** SEC-09
- **Steps:** The user chooses Sign out. The page closes the real-time connection and discards the session and cached messages.

### UC-21: Session expiry

- **Trace:** SEC-09
- **Steps:** After 8 hours the session is no longer accepted. The next request or reconnect fails with "Your session has expired." The page returns to the sign-in screen and keeps any unsent text.

### UC-22: Reach a conversation the user is no longer in

- **Trace:** FR-14, SEC-03
- **Steps:** If a user opens a conversation they have left or been removed from, the service answers "Not found". The page removes it from the list.

## 4. Message states

States the sender sees on their own messages (FR-44):

| State | Meaning | Next |
| --- | --- | --- |
| Sending | The message was handed to the service. No confirmation yet. | Sent, or Failed to send |
| Sent | The service stored the message and gave it its place in the order. | Deleted |
| Failed to send, retrying | An attempt failed. The client retries with the same ID. | Sent, or Not sent |
| Not sent | All 5 attempts failed. The user can choose Retry. | Sending |
| Deleted | The author deleted it. Text and files are gone. | None |

Delivery to other people is not shown to the sender, because read receipts were not selected.

## 5. Rules, limits, and validation

| Item | Rule | Trace |
| --- | --- | --- |
| Message length | 1 to 4,000 characters after trimming | A-31, FR-20 |
| Send rate | 30 messages per minute per user | FR-46 |
| Direct message members | Exactly 2 | FR-10 |
| Group chat members | 2 to 20 | FR-11 |
| Channel members | 1 to 100 | FR-12 |
| Channel name | 1 to 50 characters, unique ignoring case | FR-12 |
| Group name | 1 to 50 characters (optional for direct messages: none) | FR-11 |
| Attachment size | 1 byte to 25 MB | FR-24 |
| Attachments per message | Up to 5 | FR-24 |
| Allowed file types | png, jpg, jpeg, gif, webp, pdf, txt, md, csv, docx, xlsx, pptx | FR-24 |
| Page size | 50 messages per page | FR-45 |
| Search query | 2 to 100 characters, up to 50 results | FR-25 |
| User name | 3 to 32 characters: a-z, 0-9, dot, dash, underscore | FR-03 |
| Session lifetime | 8 hours | SEC-09 |
| Reconnect wait | Doubles from 1 second up to 30 seconds | UC-19 |
| Send retries | 5 attempts, waits 1, 2, 4, 8, 16 seconds | UC-06 |
| Mentions per message | Up to 20 are processed | FR-23 |
| Unsent upload cleanup | After 1 hour | FR-24 |
| Request timeout | 10 seconds, after which the request counts as failed | SLO-01 |
| Times | Stored in UTC, shown in the user's time zone | FR-30 |

## 6. Message formatting

- The service stores the text exactly as typed. The page formats it when showing it (FR-21).
- Supported: `**bold**`, `*italic*`, `` `inline code` ``, fenced code blocks, links written as `[text](https://...)`, line breaks, and @mentions.
- Only `http` and `https` links are made clickable. Links open in a new tab and do not pass the page address along.
- Raw HTML in a message is shown as plain text. It is never run.
- Plain text with none of these marks shows as typed.

## 7. Notifications

| Event | Notification record | Live signal | Trace |
| --- | --- | --- | --- |
| New message in a conversation the user is in | None | Unread count goes up. A polite announcement. A short on-screen alert if the conversation is not open. | FR-26, ACC-02 |
| Mention | Yes: "Name mentioned you in Conversation" | Bell count goes up | FR-23, FR-26 |
| Added to a conversation | Yes: "Name added you to Conversation" | Bell count goes up | FR-26 |

- A notification never contains message text (PRV-04, A-20). It names the sender and the conversation only.
- If a mentioned person has no open connection, an email notification is queued with the same wording. In the lab it is recorded and never sent (stub).
- Push notifications are not built. Their design is described in the architecture document.

## 8. Errors the user can see

| Situation | What the user sees | Service answer |
| --- | --- | --- |
| Not signed in or session expired | "Your session has expired. Sign in again." | 401 |
| Not allowed (for example a non-administrator creating a channel) | "You are not allowed to do that." | 403 |
| Conversation or message not found, or user is not a member | "Not found." | 404 |
| Invalid input | The specific problem, for example "Message is too long" | 400 |
| Name already taken, or member limit reached | The specific problem | 409 |
| File too large | "File is larger than 25 MB." | 413 |
| File type not allowed | "This file type is not allowed." | 415 |
| Sending too fast | "You are sending too fast. Try again in a few seconds." | 429 |
| Service problem | "Something went wrong. We will try again." with a reference number the user can give to support | 500 and others |

The reference number is the correlation ID of the request (OPS-05). Not being a member and the conversation not existing look the same on purpose, so that nobody can find out which conversations exist.

## 9. Accessibility behavior

| Behavior | Trace |
| --- | --- |
| Every control can be reached and used with the keyboard. Focus order follows the visual order. The focus outline is always visible. | ACC-01 |
| A "Skip to messages" link is the first item on the page. | ACC-01 |
| The message list is a labeled region. New messages are announced politely by a live region and never take focus. | ACC-02 |
| Each message exposes sender, time, and status as text, not only by color or position. | ACC-03 |
| Mentions are marked with text and style, not color alone. | ACC-03 |
| The thread panel, search results, and notification list are labeled regions, and opening them moves focus to their heading. Closing them returns focus to the button that opened them. | ACC-03 |
| Colors meet the AA contrast ratio. Text can be enlarged to 200 percent without loss. | ACC-01 |
| Buttons and fields have text labels. Icons never stand alone without a label. | ACC-03 |
| Error messages are announced when they appear. | ACC-02 |

## 10. Not specified

- Typing indicators, online presence, read receipts, message editing, voice, video, and bots are not built (see the requirements, section 9).
- Email and push delivery are stubs or designs only.
- Exact visual design, wording translations, and languages other than English are not specified.
