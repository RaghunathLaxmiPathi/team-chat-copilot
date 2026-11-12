# Functional Specifications Critique (GAO)

Date: 2026-11-11
Artifact reviewed: [chatapp.funcspecs.md](./chatapp.funcspecs.md)

> **Status at a glance**
> 8 findings: 0 High, 6 Medium, 2 Low. Disposition follows the fixed rule: Medium is Address and Low is Defer. The 6 Medium findings have been applied to the functional specs and are marked Done.

## Checks that came up clean

- **Coverage of requirements:** every functional requirement (FR-01 to FR-47) is covered by a use case, a rule table, or a section, except FR-06 (identity boundary), which is an architecture rule with no user-visible behavior.
- **Fundamentals:** accessibility (section 9), privacy (UC-12, section 7), security (roles, UC-17), and supportability (error reference number, UC-18) all have observable behavior.
- **Unstated numbers:** every limit in section 5 matches an assumption (A-31, A-23) or is marked as a default.

## Medium severity

### F-01: Direct messages "cannot change members" but deactivation removes users from all conversations

- **Description:** UC-05 says a direct message cannot change members. UC-17 says a deactivated user is removed from all conversations. These conflict for direct messages. It is also unstated whether the other person can keep writing to a direct message with a deactivated user.
- **Why it matters:** Engineers will implement this two ways. Messages to a person who can no longer read them would be lost or stored for no one.
- **Recommended action:** State that direct messages keep their two members. A deactivated user is blocked by their deactivation. The other person keeps the history and sees "former member", and new messages to that conversation are refused with a clear message.
- **Severity:** Medium
- **Disposition:** Done

### F-02: A message deleted while a user is offline would stay on that user's screen

- **Description:** UC-08 replays messages after the last number the page has. A message the page already holds and that was deleted while it was offline would not be replayed, so the page would keep showing it.
- **Why it matters:** This breaks the delete promise (A-17, FR-27: the message disappears from all users' views) and leaks deleted sensitive text.
- **Recommended action:** Have the catch-up also return the IDs of messages deleted since the page's last sync, and have the page remove them.
- **Severity:** Medium
- **Disposition:** Done

### F-03: The last-administrator rule allows a single administrator

- **Description:** UC-17 only blocks deactivating the last administrator. FR-03 requires at least two. There is also no way to make an existing user an administrator.
- **Why it matters:** The service could drop to one administrator, which recreates the single point of failure that A-30 is meant to remove.
- **Recommended action:** Block any change that leaves fewer than two active administrators. Add the ability to grant and remove the administrator role.
- **Severity:** Medium
- **Disposition:** Done

### F-04: Several devices or tabs for one user are not specified

- **Description:** Nothing says whether a user can be signed in on more than one device, or how a message sent from one device reaches the user's others.
- **Why it matters:** FR-41 requires every device to show the same order. Without a rule, a second tab misses the user's own sent messages and shows a different list.
- **Recommended action:** Allow several sessions. Deliver every message, including the user's own, to all of the user's open connections. Unread state is per user, not per device.
- **Severity:** Medium
- **Disposition:** Done

### F-05: Opening a search result at its message is not defined

- **Description:** UC-13 says choosing a result opens the conversation at that message. Loading around an older message is not described, and history paging (UC-08) only goes forward or backward from the newest.
- **Why it matters:** Without it, search results are not usable for old messages. The visible history limit for group chats (FR-15) must also hold here.
- **Recommended action:** Specify loading a page around a message (25 before and 25 after), and "load earlier" and "load later" buttons, within the user's visible history.
- **Severity:** Medium
- **Disposition:** Done

### F-06: Who may see the health and objectives pages is not specified

- **Description:** UC-18 does not say who can open the objectives and metrics pages.
- **Why it matters:** These pages reveal usage and error information. Leaving them open to anyone on the network is a security gap for a service that holds confidential data.
- **Recommended action:** Keep the basic health check open for the platform's probes. Limit the objectives and metrics pages to administrators.
- **Severity:** Medium
- **Disposition:** Done

## Low severity

### F-07: Date separators and time display in the message list are not described

- **Description:** FR-30 says times are shown in the user's time zone, but the list's date separators, and how "today" is decided, are not described.
- **Why it matters:** Cosmetic. Reasonable defaults exist.
- **Recommended action:** Show a date separator when the local date changes.
- **Severity:** Low
- **Disposition:** Defer

### F-08: Finding channels the user is not in is not described

- **Description:** Channels are joined only when an administrator adds a member. The specs do not say that non-members cannot see the list of channels.
- **Why it matters:** Minor. It follows from the membership rule, and discoverability is not requested.
- **Recommended action:** None needed now. Revisit if self-service joining is requested.
- **Severity:** Low
- **Disposition:** Defer

## Summary

| ID | Title | Severity | Disposition |
| --- | --- | --- | --- |
| F-01 | Direct messages "cannot change members" but deactivation removes users from all conversations | Medium | Done |
| F-02 | A message deleted while a user is offline would stay on that user's screen | Medium | Done |
| F-03 | The last-administrator rule allows a single administrator | Medium | Done |
| F-04 | Several devices or tabs for one user are not specified | Medium | Done |
| F-05 | Opening a search result at its message is not defined | Medium | Done |
| F-06 | Who may see the health and objectives pages is not specified | Medium | Done |
| F-07 | Date separators and time display in the message list are not described | Low | Defer |
| F-08 | Finding channels the user is not in is not described | Low | Defer |
