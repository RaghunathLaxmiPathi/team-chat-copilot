# Team Chat Application: Assumptions Critique (GAO)

Date: 2026-11-11

> **Status at a glance**
> 20 findings: 7 High, 10 Medium, 3 Low. All 17 High and Medium findings are Done and resolved in [chatapp.assumptions.md](./chatapp.assumptions.md). The 3 Low findings are Defer and were left untouched. The summary table at the end shows where each finding was resolved.

## Purpose and basis

This is a critique of the assumptions gathered so far for the team chat application. It checks whether they are a sound foundation for writing requirements and engineering a Microsoft service that meets the Fundamentals: quality, capacity, availability, resiliency, security, privacy, accessibility, and supportability.

The only source is the brainstorm conversation. No earlier assumptions document exists. Anything the owner did not answer is treated as unknown, not as a decision.

### Assumptions as stated by the owner

| Area | Stated |
| --- | --- |
| Users | Direct team only, about 10 people, sign in with Entra ID |
| Growth | Not defined. Five questions go to the requester: team-only vs adoption by other teams, compliance and retention rules, launch date and budget, ownership and on-call, external guests |
| Conversations | Direct messages, group chats (invite-based), channels |
| Message features | Plain text, markdown, threads, @mentions, attachments, search, notifications (in-app, email, push) |
| Membership | Controlled by the owner |
| Out of scope | Voice |
| Real-time | Instant push (about 1 second or less); users receive everything they missed, in order; delivery status and automatic retry |
| Accessibility | Needs unknown; deferred twice |
| Storage | Keep history forever; users can delete their own messages; departing members keep their messages and lose access immediately; chats likely contain sensitive information |
| Attachments | Retention not decided; owner asked to be asked at the end |
| Hosting, scale, security details, operations | Not yet stated |

### Checks performed

| Check | Result |
| --- | --- |
| 1. Missing assumptions needed before requirements | Findings: G-05, G-06, G-07, G-13, G-16, G-17 |
| 2. Assumptions too vague to act on | Findings: G-08, G-12 |
| 3. Confidence levels that seem unjustified | Finding: G-14 |
| 4. Contradictions | Findings: G-01, G-09, G-18 |
| 5. Missing boundary conditions and edge cases | Findings: G-10, G-15 |
| 6. Fundamentals with no assumption | Findings: G-04 (accessibility), G-06 (availability, resiliency), G-07 (supportability), G-02 and G-03 (privacy, security), G-12 (quality) |

Fundamentals coverage: capacity has one thin assumption (10 users). Security has one (Entra ID). Every other Fundamental has no assumption or a deferred one.

---

## High severity

### G-01: Keep forever contradicts users deleting their own messages

- **Description:** The owner chose to keep history forever and also chose to let users delete their own messages. Both cannot be true as written. Either deleted messages are really removed, or history is kept forever.
- **Why it matters:** Privacy and legal exposure. If a deleted message still exists in storage, backups, or search, users are told something false. Engineers will also guess which rule wins, and different parts of the system will guess differently.
- **Recommended action:** Decide which rule wins and state it. Define what "delete" means: hidden from users, removed from storage, or removed from backups, and within what time. Define whether a retention limit overrides user deletion.
- **Severity:** High
- **Disposition:** Done

### G-02: Privacy and compliance rules are unknown while sensitive content is expected

- **Description:** The owner expects sensitive content (customer data, personnel matters, credentials, confidential information) but has not said which compliance, retention, or data-handling rules apply. Those are open questions for the requester. "Keep forever" was chosen before that answer exists.
- **Why it matters:** A Microsoft service must meet privacy and data-handling obligations. Indefinite retention of sensitive data is likely to conflict with them, and it increases the impact of any breach. Retention, residency, deletion, and access requirements cannot be written until these rules are known.
- **Recommended action:** Treat "keep forever" as a placeholder, not a decision. Get the compliance and retention answers from the requester and the privacy contact before writing retention requirements. Record who owns data subject requests (access, deletion).
- **Severity:** High
- **Disposition:** Done

### G-03: Protection of sensitive data is not defined

- **Description:** No assumption covers how sensitive data is protected: encryption in transit and at rest, who can read messages (including the owner, operators, and administrators), audit logging of access, key management, or session and sign-in policy (MFA, session lifetime). Entra ID is the only security assumption.
- **Why it matters:** Security is a Fundamental, and the owner says chats will likely hold sensitive data. Without these assumptions, engineers will either under-build or invent controls with no agreed basis. Who can read direct messages is also a privacy question that employees will ask.
- **Recommended action:** State assumptions for encryption, access to message content by operators and admins, audit logging, authorization (who can read which conversation, enforced on the server), and sign-in policy. Classify the data (for example by Microsoft data classification) so controls can follow.
- **Severity:** High
- **Disposition:** Done

### G-04: Accessibility is deferred and treated as optional

- **Description:** The owner deferred accessibility needs twice and said to ask when the time comes. Accessibility needs of the 10 team members are unknown.
- **Why it matters:** Accessibility is a Fundamental, and it does not depend on whether a current team member has a known need. Instant push, threads, @mentions, and live-updating lists are the hardest features to make work for screen reader and keyboard users. Deciding late means reworking UI and interaction design already built. A service that excludes users cannot ship as a Microsoft service.
- **Recommended action:** Assume accessibility is a v1 requirement regardless of known needs. Record the target standard (for example WCAG 2.1 AA and Microsoft accessibility requirements). Add an assumption for how new messages are announced to assistive technology and for full keyboard operation. Name an owner and a date for the team's actual needs.
- **Severity:** High
- **Disposition:** Done

### G-05: Where the application runs is not stated

- **Description:** No assumption covers hosting: cloud or on-premises, which platform, which regions, and which environments (development, test, production).
- **Why it matters:** Hosting determines the availability and resiliency options, the security and compliance controls, data residency, cost, and what the operations team must run. Nearly every other Fundamental depends on it. Real-time connections and storage design also differ by platform.
- **Recommended action:** State the hosting platform, regions, and environments. If undecided, record it as an open decision with an owner. As a Microsoft service, confirm the required approved platform and compliance baseline.
- **Severity:** High
- **Disposition:** Done

### G-06: No availability or resiliency targets, despite a strong delivery promise

- **Description:** The owner requires that users receive everything they missed, in order, with instant push. That is a durability and recovery promise, but no availability target, recovery time, data-loss tolerance, or disaster recovery assumption exists.
- **Why it matters:** "Nothing is lost, in order" must hold through restarts, deployments, outages, and regional failure. Without targets, engineers cannot choose storage, replication, or failover, and cannot test the promise. Availability and resiliency are Fundamentals with no assumption.
- **Recommended action:** State an availability target (for example monthly uptime), a recovery time objective, and a recovery point objective (the amount of data loss allowed, which should be zero for acknowledged messages if the promise stands). State whether downtime during deployments is allowed and what the client does while disconnected.
- **Severity:** High
- **Disposition:** Done

### G-07: Operation, monitoring, and ownership are undefined

- **Description:** No assumption covers who runs the service, who is on call, how it is monitored, how incidents are handled, or how it is deployed and updated. Ownership after launch is an open question for the requester.
- **Why it matters:** Supportability is a Fundamental. A service holding sensitive data with no named owner has nobody to respond to an outage or a security incident. Monitoring requirements (what to measure, what alerts) also shape the design, for example message delivery latency and failed deliveries.
- **Recommended action:** Assume a named owner and on-call arrangement before launch. State the minimum monitoring: health, delivery latency, error rate, connection counts, and storage growth. State how support requests and incidents are received and handled, and how logs avoid storing message content.
- **Severity:** High
- **Disposition:** Done

---

## Medium severity

### G-08: Capacity and performance assumptions are vague or missing

- **Description:** The only capacity number is 10 users, and the growth answer was "get as much information as you can". "About 1 second or less" for delivery has no percentile, no measurement point, and no load condition. There are no assumptions for message volume, message size, attachment size, concurrent connections, or storage growth. With "keep forever", storage and search grow without bound.
- **Why it matters:** Capacity is a Fundamental. A requirement that cannot be measured cannot be tested. Indefinite retention plus search and "everything missed" replay means cost and performance get worse every month.
- **Recommended action:** State expected messages per user per day, attachment size and volume, and peak concurrent users. Define the latency target, for example 95th percentile of send-to-receive under normal load. State a growth assumption (even "stays at 10") with an owner who can confirm it.
- **Severity:** Medium
- **Disposition:** Done

### G-09: Single owner controls membership, but access must be removed immediately

- **Description:** The owner alone controls membership. The owner also wants departing members to lose access immediately. One person is a single point of failure for both onboarding and offboarding. The rules for creating and joining channels and groups beyond "me" are not stated.
- **Why it matters:** If the owner is unavailable, a departing member keeps access. That is a security gap, and a supportability gap. It also depends on one person's memory.
- **Recommended action:** Assume at least two administrators. Tie access to the Entra ID account state, so disabling the account removes access without a manual step in the app. State who may create channels and groups and who may add members.
- **Severity:** Medium
- **Disposition:** Done

### G-10: Derived copies of messages are not covered by retention or deletion

- **Description:** Search, email and push notifications, backups, replies, and attachments all hold copies of or references to messages. Nothing says what happens to them when a message is deleted, a member leaves, or retention applies. Deleting a message that has replies in a thread is also undefined.
- **Why it matters:** Sensitive content can survive in the search index, in email, or on a phone after the original is deleted. Search must also respect who may see each conversation.
- **Recommended action:** Assume deletion and retention apply to every copy, including the search index and backups, with a stated time. Assume notifications avoid message content (for example "new message from X"). Define the behavior for deleting a message that has replies.
- **Severity:** Medium
- **Disposition:** Done

### G-11: Untrusted content handling is not assumed (markdown, links, attachments)

- **Description:** Markdown and file attachments were selected, but there are no assumptions for sanitizing rendered content, limiting file size and type, scanning files for malware, or protecting access to attachments. Attachment retention is unresolved (parked by the owner).
- **Why it matters:** Unsanitized markdown can lead to script injection. Attachments are the main route for malware, and they are the largest and riskiest data stored. A flaw here exposes every user.
- **Recommended action:** Assume rendered content is sanitized, files are size- and type-limited and scanned, and attachment access follows conversation permissions. Resolve attachment retention at the end of the brainstorm, as the owner requested.
- **Severity:** Medium
- **Disposition:** Done

### G-12: Quality and delivery semantics are not defined

- **Description:** The owner asked for ordered delivery, no lost messages, and automatic retry, but did not state the delivery guarantee. Retry without a rule can produce duplicate messages. Ordering across several devices or after reconnect is not defined. No assumption covers quality in general, such as test expectations or what counts as acceptable defect levels at launch.
- **Why it matters:** Duplicates and out-of-order messages are the most common visible defects in chat. Quality is a Fundamental with no assumption. The behavior must be agreed before it can be built and tested.
- **Recommended action:** Assume the server assigns message order and each message has a client-generated unique ID so retries do not create duplicates. State the guarantee in plain words (for example: a message is shown as sent only after it is stored). State basic quality gates for launch.
- **Severity:** Medium
- **Disposition:** Done

### G-13: No stated purpose or success measure

- **Description:** The request is a single sentence. The owner did not select the question of why Microsoft Teams (or another existing tool) is not sufficient. There is no assumption about what success looks like or what this app must do that existing tools do not.
- **Why it matters:** The scope chosen (direct messages, groups, channels, threads, search, attachments, notifications) is close to an existing product. Without a purpose, scope cannot be prioritized and there is no way to judge whether the project worked, or whether it should be built.
- **Recommended action:** Record the reason this app is needed and one or two measurable success criteria. Put the "why not Teams" question to the requester.
- **Severity:** Medium
- **Disposition:** Done

### G-14: Confidence and source are not recorded, and some answers look unjustified

- **Description:** No assumption has a confidence level or a source. Several answers appear stated without basis: "about 10 users" with no growth information, "keep forever" while compliance rules are unknown, and accessibility "ask me at that time" while needs are unknown.
- **Why it matters:** Requirements will treat every answer as settled. Guesses will be built in as facts, and nobody will know which ones to recheck.
- **Recommended action:** Record, for each assumption, a confidence level (high, medium, low), who said it, and how it will be verified. Mark "keep forever", user count, and growth as low confidence until verified.
- **Severity:** Medium
- **Disposition:** Done

### G-15: Boundary conditions and edge cases are not assumed

- **Description:** Nothing is stated for limits and edge cases: maximum message length, rate limits, maximum members per group or channel, very long history, and a user who returns after a long absence ("everything missed" could be very large with forever retention). Also undefined: how a departed member's messages are shown, what happens when an Entra account is deleted, whether a person added to a group or channel sees earlier messages, and how time zones are displayed.
- **Why it matters:** These cases decide the data model and the user experience, and they are expensive to change after data exists. The "everything missed, in order" promise has no stated upper bound.
- **Recommended action:** Assume explicit limits and behaviors for each case listed. Decide whether new members see history. Bound the catch-up on reconnect (for example, load in pages).
- **Severity:** Medium
- **Disposition:** Done

### G-16: Client platforms are not stated

- **Description:** No assumption says whether users use a web app, desktop app, mobile app, or several. Push notifications were selected, which implies at least some device-level delivery.
- **Why it matters:** The platform decides the real-time approach, the notification mechanism, accessibility testing scope, and the security of data stored on devices (sensitive messages cached on personal phones).
- **Recommended action:** State supported platforms and browsers for v1, and whether messages may be stored on user devices.
- **Severity:** Medium
- **Disposition:** Done

### G-17: Identity boundary may not match the likely user population

- **Description:** Sign-in is Entra ID and the users are the direct team. Whether external guests or contractors join, and whether other teams adopt the app, are open questions. Entra ID sign-in for the organization does not by itself cover guests, and a team-only design may not extend to other teams without rework.
- **Why it matters:** Tenancy and the authorization model are hard to change later. Guests change the privacy and security posture.
- **Recommended action:** Assume internal users of one organization for v1 and record the guest and multi-team questions as blocking open items. Design authorization so that adding a second team does not require a rewrite.
- **Severity:** Medium
- **Disposition:** Done

---

## Low severity

### G-18: "Plain text only" and "markdown" were both selected

- **Description:** The message features include both plain text only and formatting or markdown. These conflict.
- **Why it matters:** It is a small ambiguity, but requirements need one answer. It is easy to resolve.
- **Recommended action:** Assume markdown is the single supported format (plain text is a subset) and confirm.
- **Severity:** Low
- **Disposition:** Defer

### G-19: Typing indicators and presence are undecided

- **Description:** The owner did not answer whether typing indicators or online presence are wanted.
- **Why it matters:** They add constant traffic and accessibility work, and add little for 10 people. Leaving them out of v1 has little cost.
- **Recommended action:** Assume neither is in v1 unless the owner asks for them.
- **Severity:** Low
- **Disposition:** Defer

### G-20: Video, bots, and integrations are neither in nor out of scope

- **Description:** Only voice was excluded. Video, screen sharing, bots, and integrations are not mentioned.
- **Why it matters:** Unstated scope tends to be added later by assumption. The effect on v1 is small.
- **Recommended action:** Assume they are out of scope for v1 and confirm.
- **Severity:** Low
- **Disposition:** Defer

---

## Summary

| ID | Title | Severity | Disposition | Resolved in |
| --- | --- | --- | --- | --- |
| G-01 | Keep forever contradicts users deleting their own messages | High | Done | A-15, A-16, A-17 |
| G-02 | Privacy and compliance rules unknown while sensitive content is expected | High | Done | A-16, A-18 |
| G-03 | Protection of sensitive data not defined | High | Done | A-22 |
| G-04 | Accessibility deferred and treated as optional | High | Done | A-24 |
| G-05 | Where the application runs is not stated | High | Done | A-25 |
| G-06 | No availability or resiliency targets despite a strong delivery promise | High | Done | A-26, A-27 |
| G-07 | Operation, monitoring, and ownership undefined | High | Done | A-32, A-33 |
| G-08 | Capacity and performance assumptions vague or missing | Medium | Done | A-28, A-29 |
| G-09 | Single owner controls membership, but access must be removed immediately | Medium | Done | A-30 |
| G-10 | Derived copies of messages not covered by retention or deletion | Medium | Done | A-17, A-20 |
| G-11 | Untrusted content handling not assumed (markdown, links, attachments) | Medium | Done | A-23 (attachment retention still an open question) |
| G-12 | Quality and delivery semantics not defined | Medium | Done | A-13, A-14 |
| G-13 | No stated purpose or success measure | Medium | Done | A-05 |
| G-14 | Confidence and source not recorded; some answers look unjustified | Medium | Done | A-02, A-16, A-28, A-34 |
| G-15 | Boundary conditions and edge cases not assumed | Medium | Done | A-19, A-31 |
| G-16 | Client platforms not stated | Medium | Done | A-09 |
| G-17 | Identity boundary may not match the likely user population | Medium | Done | A-04 |
| G-18 | "Plain text only" and "markdown" both selected | Low | Defer | Not addressed |
| G-19 | Typing indicators and presence undecided | Low | Defer | Not addressed |
| G-20 | Video, bots, and integrations neither in nor out of scope | Low | Defer | Not addressed |
