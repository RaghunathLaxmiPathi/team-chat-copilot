# Team Chat Application: Assumptions

Date: 2026-11-11

> **Status at a glance**
> 34 assumptions: 9 High, 7 Medium, 18 Low confidence. 10 come from the owner as stated, 5 are owner statements that were revised, and 19 were proposed to close gaps found in the critique ([chatapp.assumptions.gao.md](./chatapp.assumptions.gao.md)). Most numbers here are starting values, not decisions.
>
> **Most important to confirm first**
> 1. Retention period and compliance rules (A-16, A-18). "Keep forever" is only a placeholder.
> 2. Accessibility needs and owner (A-24). Accessibility is required in v1 regardless.
> 3. Hosting, availability, and recovery targets (A-25 to A-27).
> 4. Service ownership and on-call (A-32).
> 5. Whether guests or other teams will use the app (A-04).

## Contents

1. [How to read this document](#how-to-read-this-document)
2. [Overview table](#overview-table)
3. [Assumptions by area](#1-users-and-identity): users and identity, purpose and scope, real-time delivery, data and retention, security and privacy, accessibility, hosting and resiliency, capacity, membership, boundary conditions, operations, tracking
4. [Open questions](#open-questions)

## How to read this document

Each assumption has a Title, the Assumption itself, a Confidence level, and the Risk if Wrong. Each also lists its Source and, for items added after the critique in [chatapp.assumptions.gao.md](./chatapp.assumptions.gao.md), the finding it addresses.

Confidence levels:

- **High:** stated by the owner and unlikely to change, or required by policy.
- **Medium:** stated by the owner but not verified, or a reasonable default.
- **Low:** a proposed value or a placeholder. Nobody has confirmed it. It must be verified before it becomes a requirement.

Sources:

- **Owner:** stated by the owner during the brainstorm.
- **Proposed:** added to close a gap found in the critique. The value is a starting point for the owner to confirm or change.
- **Owner, revised:** the owner stated it, and the critique added detail or changed it. The entry says what changed.

Proposed values are not decisions. Every Low confidence item needs confirmation, and the Open Questions section lists who or what can confirm them.

## Overview table

| ID | Title | Confidence | Source |
| --- | --- | --- | --- |
| A-01 | Users are the owner's direct team | High | Owner |
| A-02 | About 10 users at launch | Low | Owner |
| A-03 | Users sign in with Entra ID | High | Owner |
| A-04 | Internal users of one organization only in v1 | Low | Proposed |
| A-05 | Purpose and success measures | Low | Proposed |
| A-06 | Conversation types | High | Owner |
| A-07 | Message features | Medium | Owner |
| A-08 | Voice is out of scope | High | Owner |
| A-09 | Client platforms | Low | Proposed |
| A-10 | Instant delivery | High | Owner |
| A-11 | Users receive everything they missed, in order | High | Owner |
| A-12 | Delivery status and automatic retry | High | Owner |
| A-13 | Delivery semantics | Medium | Proposed |
| A-14 | Quality gates for launch | Low | Proposed |
| A-15 | Users can delete their own messages | Medium | Owner, revised |
| A-16 | Retention period (placeholder) | Low | Owner, revised |
| A-17 | Meaning of delete | Low | Proposed |
| A-18 | Privacy and compliance obligations | Low | Proposed |
| A-19 | Departing members | Medium | Owner, revised |
| A-20 | Derived copies follow the same rules | Medium | Proposed |
| A-21 | Chats likely contain sensitive information | High | Owner |
| A-22 | Protection of sensitive data | Low | Proposed |
| A-23 | Untrusted content is handled safely | Low | Proposed |
| A-24 | Accessibility is a v1 requirement | Medium | Proposed |
| A-25 | Hosting platform and environments | Low | Proposed |
| A-26 | Availability target | Low | Proposed |
| A-27 | Durability and recovery targets | Low | Proposed |
| A-28 | Expected load | Low | Proposed |
| A-29 | Latency target | Medium | Owner, revised |
| A-30 | More than one administrator | Low | Owner, revised |
| A-31 | Limits and edge cases | Low | Proposed |
| A-32 | Ownership and on-call | Low | Proposed |
| A-33 | Monitoring and logging | Low | Proposed |
| A-34 | Confidence and source are recorded for every assumption | High | Proposed |

---

## 1. Users and identity

### A-01: Users are the owner's direct team

- **Assumption:** The users are the members of the owner's direct team only.
- **Confidence:** High
- **Risk if Wrong:** If other teams or the wider organization use the app, the capacity, authorization, and support needs grow, and design choices made for one team may need rework. See A-04 and the open questions.
- **Source:** Owner

### A-02: About 10 users at launch

- **Assumption:** There are about 10 users at launch.
- **Confidence:** Low
- **Risk if Wrong:** The owner gave the number but not the basis, and growth is unknown. If the real number is much higher, the capacity assumptions in section 8 are too small.
- **Source:** Owner

### A-03: Users sign in with Entra ID

- **Assumption:** Users sign in with their existing corporate identity (Microsoft Entra ID). The app does not create or store its own passwords.
- **Confidence:** High
- **Risk if Wrong:** If separate accounts are needed (for example for guests), the app must handle passwords, recovery, and MFA, which is a large security burden.
- **Source:** Owner

### A-04: Internal users of one organization only in v1

- **Assumption:** In v1, all users are internal members of one organization signing in through one Entra ID tenant. There are no external guests or contractors. Authorization is based on per-conversation membership, so that adding another team later does not need a redesign.
- **Confidence:** Low
- **Risk if Wrong:** Whether guests join, or other teams adopt the app, is an open question for the requester. If either is true, tenancy, the authorization model, and the privacy position change. These are hard to change once data exists.
- **Source:** Proposed
- **Addresses:** G-17

---

## 2. Purpose and scope

### A-05: Purpose and success measures

- **Assumption:** The reason for building this app instead of using an existing tool (for example Microsoft Teams) is not yet known and must be recorded before requirements are written. Until the requester answers, the proposed success measures are: all team members use the app weekly after launch, no acknowledged message is lost, and 95 percent of messages arrive within 1 second under normal load.
- **Confidence:** Low
- **Risk if Wrong:** Without a purpose, scope cannot be prioritized and there is no way to judge whether the project worked. The chosen scope is close to an existing product, so the project may duplicate a tool the team already has.
- **Source:** Proposed
- **Addresses:** G-13

### A-06: Conversation types

- **Assumption:** The app supports direct messages (1:1), group chats (small, ad hoc, invite-based), and channels (named, long-lived, topic-based).
- **Confidence:** High
- **Risk if Wrong:** Each type adds work for permissions, history, and notifications. Missing one means the app does not meet the request, and adding one later needs data model changes.
- **Source:** Owner

### A-07: Message features

- **Assumption:** The owner selected these message features: plain text only, formatting or markdown, replies or threads, @mentions, file and image attachments, search across history, and notifications (in-app, email, or push).
- **Confidence:** Medium
- **Risk if Wrong:** Each feature adds security, storage, and accessibility work. Features not in this list are not in v1.
- **Source:** Owner

### A-08: Voice is out of scope

- **Assumption:** Voice is out of scope.
- **Confidence:** High
- **Risk if Wrong:** Voice would need real-time media infrastructure and would change the architecture.
- **Source:** Owner

### A-09: Client platforms

- **Assumption:** v1 is a web application that works in current versions of Microsoft Edge, Google Chrome, Mozilla Firefox, and Apple Safari. There is no native mobile or desktop client in v1. Push notifications use browser web push. The app stores no message content on a device beyond the normal session cache, and the cache is cleared at sign-out.
- **Confidence:** Low
- **Risk if Wrong:** The platform decides the real-time approach, the notification method, accessibility testing scope, and how sensitive messages are protected on personal devices. A mobile client would add device storage and push risks.
- **Source:** Proposed
- **Addresses:** G-16

---

## 3. Real-time messaging and delivery

### A-10: Instant delivery

- **Assumption:** Messages are pushed to recipients as they are sent. The target is described in A-29 as a measurable latency.
- **Confidence:** High
- **Risk if Wrong:** If a few seconds of delay is acceptable, a simpler design would work. If it is not, the app needs persistent connections and a reconnect strategy.
- **Source:** Owner

### A-11: Users receive everything they missed, in order

- **Assumption:** A user who was offline or disconnected receives every message they missed when they return, in the original order.
- **Confidence:** High
- **Risk if Wrong:** This is a durability promise. If it cannot be kept through restarts, deployments, and outages, users lose trust. See A-26 and A-27 for the targets that support it.
- **Source:** Owner

### A-12: Delivery status and automatic retry

- **Assumption:** The sender sees whether a message was delivered, and the app retries automatically after a failure.
- **Confidence:** High
- **Risk if Wrong:** Without a rule for duplicates, retries can create duplicate messages. See A-13.
- **Source:** Owner

### A-13: Delivery semantics

- **Assumption:** The server assigns the order of messages in a conversation. Every message carries a unique ID created by the sender, so a retry never creates a duplicate. A message is shown as sent only after the server has stored it. Order is the same on every device. In plain words: each message appears once, in the same order, for everyone.
- **Confidence:** Medium
- **Risk if Wrong:** Duplicate or out-of-order messages are the most common visible defect in chat apps. Adding these rules after the data model exists is costly.
- **Source:** Proposed
- **Addresses:** G-12

### A-14: Quality gates for launch

- **Assumption:** Before launch there are automated tests for message ordering, duplicate prevention, reconnect and catch-up, and permission checks. There are no known High severity defects at launch. Accessibility checks (A-24) are part of the gates.
- **Confidence:** Low
- **Risk if Wrong:** Without stated gates, quality is judged by opinion and defects in the core promises (A-11, A-12) can ship unnoticed.
- **Source:** Proposed
- **Addresses:** G-12

---

## 4. Data, retention, and deletion

### A-15: Users can delete their own messages

- **Assumption:** A user can delete a message they wrote. Deletion takes precedence over retention (see A-17 and A-16).
- **Confidence:** Medium
- **Risk if Wrong:** If deletion were not possible, a mistaken or sensitive message (for example a shared password) could not be removed without manual database work.
- **Source:** Owner, with the precedence rule Proposed
- **Addresses:** G-01

### A-16: Retention period (placeholder)

- **Assumption:** The owner said history is kept forever. This is a placeholder, not a decision. The retention period is set by the compliance and retention rules that the requester must provide (see A-18). Until then, no requirement is written that depends on "forever", and the design must support a configurable retention period.
- **Confidence:** Low
- **Risk if Wrong:** Keeping sensitive data forever raises the impact of a breach and is likely to conflict with privacy and retention obligations. Storage and search cost also grow without limit.
- **Source:** Owner, revised by Proposed
- **Addresses:** G-01, G-02, G-14

### A-17: Meaning of delete

- **Assumption:** When a user deletes a message: it disappears from all users' views immediately; the content is removed from primary storage and from the search index within 24 hours; the content is removed from backups when those backups expire, and backups expire within 35 days. A deleted message that has replies is replaced in the thread by a "message deleted" placeholder, and the replies stay. If the owner or a legal rule requires a different period, that rule wins.
- **Confidence:** Low
- **Risk if Wrong:** If deleted content survives in storage, search, or backups beyond what users are told, the app misleads users and may break privacy obligations. If the periods are too short for the backup system, they cannot be met.
- **Source:** Proposed
- **Addresses:** G-01, G-10

### A-18: Privacy and compliance obligations

- **Assumption:** The service follows Microsoft privacy and data-handling requirements. The specific compliance, retention, data residency, and data subject request rules are not yet known and must come from the requester and the privacy contact before retention and handling requirements are written. A named person owns handling of data access and deletion requests.
- **Confidence:** Low
- **Risk if Wrong:** The owner expects sensitive content. Without the real rules, retention, deletion, residency, and access requirements may be wrong, and the service could be non-compliant.
- **Source:** Proposed
- **Addresses:** G-02

### A-19: Departing members

- **Assumption:** When someone leaves the team, their messages stay and their access is removed immediately. Messages from a departed member show the member's name with the label "former member". If an Entra account is deleted, the stored display name is kept so history remains readable.
- **Confidence:** Medium
- **Risk if Wrong:** If access is not removed immediately, a departed member can read sensitive chats. If their messages were removed, conversations lose meaning.
- **Source:** Owner, with the display behavior Proposed
- **Addresses:** G-15

### A-20: Derived copies follow the same rules

- **Assumption:** Retention and deletion apply to every copy of a message: the search index, notification records, replies, and backups. Search results show only conversations the user is a member of. Email and push notifications do not contain message text. They say only that a new message arrived and who sent it.
- **Confidence:** Medium
- **Risk if Wrong:** Sensitive content can survive in the search index or appear in email or on a phone after the original is deleted. A search index that ignores permissions leaks private conversations.
- **Source:** Proposed
- **Addresses:** G-10

---

## 5. Security and privacy

### A-21: Chats likely contain sensitive information

- **Assumption:** Chats are likely to contain sensitive information, such as customer data, personnel matters, credentials, and confidential business information.
- **Confidence:** High
- **Risk if Wrong:** If the content is less sensitive than assumed, the controls cost more than needed. If it is more sensitive, the controls in A-22 may not be enough.
- **Source:** Owner

### A-22: Protection of sensitive data

- **Assumption:** The data is classified as Confidential (Microsoft data classification), and the controls follow from that. All connections use TLS, and stored data, including attachments and backups, is encrypted at rest with managed keys. Authorization is checked on the server for every request: a user can read a conversation only if they are a member. Administrators and operators have no routine access to message content. Any emergency access is approved, logged, and reviewed. Administrative actions and permission changes are written to an audit log. Sign-in follows the organization's Entra ID policy, including multifactor authentication.
- **Confidence:** Low
- **Risk if Wrong:** With sensitive content expected, missing or weak controls can expose confidential data and break employee trust. Engineers without an agreed baseline will invent their own.
- **Source:** Proposed
- **Addresses:** G-03

### A-23: Untrusted content is handled safely

- **Assumption:** Markdown and links are sanitized before display so no script can run. Attachments have a size limit of 25 MB and an allowed file type list. Every attachment is scanned for malware before others can open it. Access to an attachment follows the same membership rules as its conversation. Attachment retention is an open item that the owner asked to settle at the end of the brainstorm (see Open Questions). Until it is decided, attachments follow the same retention and deletion rules as messages.
- **Confidence:** Low
- **Risk if Wrong:** Unsanitized markdown allows script injection. Unscanned attachments are the main route for malware, and a flaw here exposes every user. The size and type limits are proposed values.
- **Source:** Proposed
- **Addresses:** G-11

---

## 6. Accessibility

### A-24: Accessibility is a v1 requirement

- **Assumption:** Accessibility is required in v1 whether or not a current team member has a known need. The app meets WCAG 2.1 level AA and Microsoft accessibility requirements. It is fully usable by keyboard. New messages are announced to screen readers politely, without interrupting the user. Threads, @mentions, and message lists have accessible structure and labels. The team's actual accessibility needs are an open item with a named owner and a date.
- **Confidence:** Medium
- **Risk if Wrong:** Instant push, threads, and live-updating lists are the hardest features to make accessible. If accessibility is decided late, the interface must be reworked, and a service that excludes users cannot ship as a Microsoft service. The exact standard version is to be confirmed.
- **Source:** Proposed
- **Addresses:** G-04

---

## 7. Hosting, availability, and resiliency

### A-25: Hosting platform and environments

- **Assumption:** The service runs on Microsoft Azure, in approved regions that meet the data residency rules once A-18 is answered. There are separate development, test, and production environments. Production data is never copied to development or test.
- **Confidence:** Low
- **Risk if Wrong:** Hosting decides the availability options, security and compliance controls, data residency, cost, and what the operations team must run. Nearly every other Fundamental depends on it.
- **Source:** Proposed
- **Addresses:** G-05

### A-26: Availability target

- **Assumption:** The monthly availability target is 99.9 percent for sending and receiving messages. Deployments do not cause message loss. During a deployment or short outage, clients reconnect automatically and keep unsent messages ready to retry.
- **Confidence:** Low
- **Risk if Wrong:** Without a target, engineers cannot choose redundancy or deployment methods, and nobody can say whether the service is meeting expectations. The 99.9 percent figure is a proposed starting value.
- **Source:** Proposed
- **Addresses:** G-06

### A-27: Durability and recovery targets

- **Assumption:** The recovery point objective is zero for acknowledged messages: once the sender is told a message was delivered, it is stored durably in more than one location. The recovery time objective is 4 hours for a full regional failure. Backups are taken at least daily, and restores are tested at least every quarter.
- **Confidence:** Low
- **Risk if Wrong:** The promise that users receive everything they missed (A-11) cannot be tested or kept without these targets. If the targets are not met, messages can be lost during an outage.
- **Source:** Proposed
- **Addresses:** G-06

---

## 8. Capacity and performance

### A-28: Expected load

- **Assumption:** For v1, the team stays at about 10 users. Each user sends about 200 messages a day, so about 2,000 messages a day in total, averaging 1 KB each. The team shares about 20 attachments a day, averaging 2 MB. Peak concurrent connections are 10. Text storage grows by less than 1 GB a year. Attachments, at about 15 GB a year, are the main driver of storage growth. Growth beyond 10 users is an open question for the requester.
- **Confidence:** Low
- **Risk if Wrong:** Capacity is a Fundamental. If real use is much higher, storage, search, and connection limits will be too small. If retention stays "forever" (A-16), storage and search grow without limit.
- **Source:** Proposed
- **Addresses:** G-08, G-14

### A-29: Latency target

- **Assumption:** At least 95 percent of messages arrive at every online recipient within 1 second of the sender pressing send, measured from the server receiving the message to the recipient's client receiving it, under normal load.
- **Confidence:** Medium
- **Risk if Wrong:** "About 1 second or less" cannot be measured or tested as stated. Without a percentile and a measurement point, the target can be argued either way.
- **Source:** Owner, made measurable by Proposed
- **Addresses:** G-08

---

## 9. Membership and administration

### A-30: More than one administrator

- **Assumption:** There are at least two administrators. Access is tied to the Entra ID account: when an account is disabled or removed from the team group, the user loses access automatically, without a manual step in the app. Any team member can create a group chat and invite others. Administrators create channels and manage channel membership.
- **Confidence:** Low
- **Risk if Wrong:** The owner alone controlling membership is a single point of failure. If the owner is unavailable, a departing member keeps access, which is a security gap, and new members cannot be added.
- **Source:** Owner (owner controls membership), revised by Proposed
- **Addresses:** G-09

---

## 10. Boundary conditions

### A-31: Limits and edge cases

- **Assumption:** A message can be up to 4,000 characters. A user can send up to 30 messages a minute. A group chat has up to 20 members, and a channel up to 100 members. On reconnect, missed messages load in pages of 50, newest first. A person who joins a channel sees its earlier history. A person added to a group chat sees only messages sent after they joined. Times are stored in UTC and shown in each user's own time zone.
- **Confidence:** Low
- **Risk if Wrong:** These limits shape the data model and the user experience and are costly to change once data exists. "Everything missed, in order" has no upper bound without paging, especially if history is kept long.
- **Source:** Proposed
- **Addresses:** G-15

---

## 11. Operations and supportability

### A-32: Ownership and on-call

- **Assumption:** A named service owner and an on-call rotation exist before launch. Incidents and support requests have a defined path, including how security incidents are reported. A runbook covers common failures, and deployment and updates are automated.
- **Confidence:** Low
- **Risk if Wrong:** A service that holds sensitive data with no named owner has nobody to respond to an outage or a security incident. Ownership after launch is an open question for the requester.
- **Source:** Proposed
- **Addresses:** G-07

### A-33: Monitoring and logging

- **Assumption:** The service monitors health, message delivery latency, delivery failures, error rate, connection counts, and storage growth, and alerts the on-call person when targets (A-26, A-29) are at risk. Logs contain no message content.
- **Confidence:** Low
- **Risk if Wrong:** Without monitoring, outages and slow delivery are found by users. Logs that contain message text would leak the sensitive data the service is meant to protect.
- **Source:** Proposed
- **Addresses:** G-07

---

## 12. Assumption tracking

### A-34: Confidence and source are recorded for every assumption

- **Assumption:** Every assumption in this document has a confidence level and a source. Every Low confidence item must be confirmed by the owner or the requester before it becomes a requirement. The Open Questions section lists the main ones. Three owner statements are treated as Low confidence until verified: keep history forever (A-16), about 10 users with no stated growth (A-02, A-28), and the team's accessibility needs, which the owner has not yet stated (A-24).
- **Confidence:** High
- **Risk if Wrong:** If confidence is not recorded, guesses are built into requirements as facts and nobody knows which ones to recheck.
- **Source:** Proposed
- **Addresses:** G-14

---

## Open questions

These need an answer from the owner or the requester. They are the five questions the owner chose to take to the requester, plus the items raised in the critique.

| Question | Who answers | Affects |
| --- | --- | --- |
| Is this expected to stay team-only, or could other teams adopt it? | Requester | A-01, A-04, A-28 |
| Are there compliance, retention, or data-handling rules we must follow? | Requester and privacy contact | A-16, A-17, A-18, A-22 |
| Is there a target launch date or a fixed budget? | Requester | A-25, A-26 |
| Who owns the service after launch and is on call for it? | Requester | A-32, A-33 |
| Will any team members be external guests or contractors? | Requester | A-04 |
| Why is Microsoft Teams or another existing tool not sufficient? | Requester | A-05 |
| What are the team's accessibility needs, and who owns finding out? | Owner | A-24 |
| How long should attachments be kept, and should they follow the same rules as messages? | Owner (asked to be asked at the end) | A-23 |
| Which hosting regions and compliance baseline apply? | Requester and platform owner | A-25 |
| Do the proposed numbers (availability, recovery, limits, load) match what the team expects? | Owner | A-26 to A-29, A-31 |
