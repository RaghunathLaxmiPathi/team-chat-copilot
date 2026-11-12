# Architecture Specifications Critique (GAO)

Date: 2026-11-11
Artifact reviewed: [chatapp.archspecs.md](./chatapp.archspecs.md)

> **Status at a glance**
> 8 findings: 0 High, 5 Medium, 3 Low. Disposition follows the fixed rule: Medium is Address and Low is Defer. The 5 Medium findings have been applied to the architecture document and are marked Done.

## Checks that came up clean

- **Endpoint coverage:** every endpoint in section 6 has a sequence diagram in section 8, and every real-time flow (connect and resume, push and confirm, membership change, deactivation, deletion for online and offline users, queue overflow, token expiry) has one.
- **Stack constraint:** nothing in the stack needs a separate database server, broker, or container to run locally.
- **Lab shortcuts:** each shortcut in section 11.1 names a production alternative and a mitigation. No shortcut was found that is missing from the list.
- **Traceability:** every design decision (DD-01 to DD-24) names a requirement or assumption.
- **SLO coverage:** both SLOs are covered at every percentile and every window, with measurement method, minimum sample rule, and budget.

## Medium severity

### AR-01: The connect flow counted client-side refusals as failures

- **Description:** Diagram 8.26 recorded a failed request when a connection was refused for an invalid token, an expired token, or a deactivated user. SLO-01 excludes client errors.
- **Why it matters:** Expired sessions and deactivations would lower the Success Rate even though the service worked correctly. The document contradicted its own requirement.
- **Recommended action:** State that refusals for token or access reasons are not counted.
- **Severity:** Medium
- **Disposition:** Done

### AR-02: The latency budget has no stated basis for its network figures

- **Description:** The "delivery part" of the latency budget assumes client network times that were not written down.
- **Why it matters:** A budget that looks measured but is a guess gives false confidence, especially at P99.
- **Recommended action:** State the assumed client round-trip times and say they must be replaced by measured values.
- **Severity:** Medium
- **Disposition:** Done

### AR-03: Conversations added or removed while offline are not replayed

- **Description:** The resume flow replays messages for the conversations the client lists. Events for being added to or removed from a conversation while offline are not replayed, and the document did not say how the client finds out.
- **Why it matters:** A removed user could keep seeing a conversation in the list, and an added user would not see a new one until a refresh.
- **Recommended action:** Require the client to reload its conversation list over HTTP before sending the resume.
- **Severity:** Medium
- **Disposition:** Done

### AR-04: The deletion catch-up could miss a deletion made during the resume

- **Description:** The deleted-message list uses the server time of the last sync. If that time were taken after reading, a message deleted during the read could be missed on the next sync.
- **Why it matters:** A deleted message could stay on an offline client, which breaks the delete promise.
- **Recommended action:** Take the server time before any reading starts.
- **Severity:** Medium
- **Disposition:** Done

### AR-05: A client message ID reused in another conversation is not handled

- **Description:** Duplicate detection is by sender and client message ID. If the same ID were used for a different conversation, the service would return a message from the other conversation.
- **Why it matters:** It would return the wrong message, and for a deliberate caller it blurs conversation boundaries.
- **Recommended action:** Refuse that case with a conflict.
- **Severity:** Medium
- **Disposition:** Done

## Low severity

### AR-06: A reply may be visible when its original is not

- **Description:** A person who joined a group chat after an original message can see a later reply to it but not the original. The thread view would answer 404 for the root.
- **Why it matters:** An edge case with a small effect. The interface can show "Replying to an earlier message".
- **Recommended action:** Define the thread view for this case when the interface is refined.
- **Severity:** Low
- **Disposition:** Defer

### AR-07: Who may download an attachment before it is sent is not stated

- **Description:** An uploaded file that is not yet attached to a message is not covered by the download rule, which requires a visible message.
- **Why it matters:** Minor. The uploader needs a preview, and no one else needs access.
- **Recommended action:** Allow only the uploader to open an unsent attachment.
- **Severity:** Low
- **Disposition:** Defer

### AR-08: Growth of the objectives counts, audit log, and notifications is not bounded

- **Description:** There is no pruning rule for the per-minute counts older than 28 days, the audit log, or old notifications.
- **Why it matters:** At 10 users the growth is tiny. Over years it is not zero.
- **Recommended action:** Add pruning rules when the retention answer arrives.
- **Severity:** Low
- **Disposition:** Defer

## Summary

| ID | Title | Severity | Disposition |
| --- | --- | --- | --- |
| AR-01 | The connect flow counted client-side refusals as failures | Medium | Done |
| AR-02 | The latency budget has no stated basis for its network figures | Medium | Done |
| AR-03 | Conversations added or removed while offline are not replayed | Medium | Done |
| AR-04 | The deletion catch-up could miss a deletion made during the resume | Medium | Done |
| AR-05 | A client message ID reused in another conversation is not handled | Medium | Done |
| AR-06 | A reply may be visible when its original is not | Low | Defer |
| AR-07 | Who may download an attachment before it is sent is not stated | Low | Defer |
| AR-08 | Growth of the objectives counts, audit log, and notifications is not bounded | Low | Defer |
