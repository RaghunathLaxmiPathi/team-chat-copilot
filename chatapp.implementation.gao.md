# Implementation Critique (GAO)

Date: 2026-11-11
Artifact reviewed: the working application in [chatapp/](./chatapp) and its [README](./chatapp/README.md)

> **Status at a glance**
> 10 findings: 0 High, 6 Medium, 4 Low. Disposition follows the fixed rule: Medium is Address and Low is Defer.
> Three Medium findings were found and fixed during the build and are marked Done. The other three Medium findings need a person's decision or a manual check, so they stay at Address.
> Evidence: 105 automated tests pass, the real server was started and used through the browser, live weather and time were checked against the real service, and free-text questions were answered by a real model (Llama 3.2 3B through Ollama) running on this computer.

## Checks that came up clean

- **Requirements coverage:** every functional requirement, SLO, security, privacy, and supportability requirement that can be tested locally has an automated test.
- **Stack constraint:** it runs with two commands. No database server, broker, or container is needed.
- **Authorization:** non-members and missing items give the same answer everywhere, and administrators cannot read channels they are not in (tests T-14, T-73, and the channel-management test).
- **Latency (service part):** 120 acknowledged deliveries measured at the 10 ms bucket at every percentile against targets of 200 to 2,000 ms. 20,000 deliveries across 100 connections stayed within every target.

## Medium severity

### I-01: The web server's own log line printed the full session token

- **Description:** The real-time connection carries the session token in its address. The web server (uvicorn) logs that address itself, so tokens appeared in the server log. My tests only looked at the application's own log lines and missed it. I found it by reading the real server's output.
- **Why it matters:** A token in a log is a stolen sign-in for anyone who can read the log (PRV-03, SEC-03).
- **Recommended action:** Redact tokens in every log line and test it.
- **Severity:** Medium
- **Disposition:** Done

### I-02: A deletion made in the same millisecond as a sync could be missed

- **Description:** The catch-up compared deletion time with "after" the client's last sync time. A deletion in the very same millisecond was not reported, so a deleted message could stay on an offline person's screen. It showed up as an occasional test failure.
- **Why it matters:** It breaks the delete promise (FR-27, DD-12).
- **Recommended action:** Compare with "at or after". Repeats are harmless.
- **Severity:** Medium
- **Disposition:** Done

### I-03: The design documents said bots were out of scope

- **Description:** The requirements and architecture documents did not cover the assistant, its default of joining every group and replying to everything, or its use of history and live data.
- **Why it matters:** The documents and the product would disagree, and the privacy impact was not recorded.
- **Recommended action:** Add the assistant to the requirements (section 10) and the architecture (section 11.2) with its risks.
- **Severity:** Medium
- **Disposition:** Done

### I-04: Live lookups send a place name to a free third-party service

- **Description:** Weather and the time in unknown places use Open-Meteo. Only the place name is sent, and it can be switched off, but it is on by default and no privacy review has covered it (A-18 is still open).
- **Why it matters:** Any data leaving a Microsoft service needs an approved path. A place name is low risk, but the rule applies to the route, not just the data.
- **Recommended action:** Get the privacy contact's decision. Until then, set `CHATAPP_COPILOT_WEB=false` for any shared deployment.
- **Severity:** Medium
- **Disposition:** Address

### I-05: The interface was checked by hand once, and accessibility was not audited

- **Description:** The page was exercised in the browser for sign-in, the Copilot chat, and live replies. There are no automated browser tests, and the manual checks M-01 to M-03 (keyboard, screen reader, contrast and zoom) have not been done.
- **Why it matters:** Accessibility is a Fundamental and a launch requirement (A-24). Layout and focus bugs are likely to exist.
- **Recommended action:** Run the three manual checks and add Accessibility Insights and browser tests to the build.
- **Severity:** Medium
- **Disposition:** Address

### I-06: Copilot joining every group and replying to everything is on by default for everyone

- **Description:** It follows the owner's instruction, but the team has not agreed to it. Anyone can switch their own replies off, but the assistant stays a member of every group chat and channel and counts as a reader of them.
- **Why it matters:** It changes who can see what in every conversation, and it can be noisy.
- **Recommended action:** Confirm with the team before sharing the service. Consider an opt-in per group and a visible badge. `CHATAPP_COPILOT_AUTO_JOIN=false` and `CHATAPP_COPILOT_AUTO_DEFAULT=false` turn the defaults off.
- **Severity:** Medium
- **Disposition:** Address

## Low severity

### I-07: The test specification does not list the assistant tests and numbers differ

- **Description:** The test specification lists 71 cases. The suite has 105 tests, including 32 for the assistant. A few specified cases are merged into others.
- **Why it matters:** The document and the suite are out of step.
- **Recommended action:** Regenerate the specification from the suite.
- **Severity:** Low
- **Disposition:** Defer

### I-08: The session token is kept in the browser's session storage

- **Description:** It is cleared when the tab closes, but script on the page could read it. The strict content policy and the safe renderer reduce the chance of script running.
- **Why it matters:** An accepted lab shortcut. Production uses Entra ID tokens and secure cookies.
- **Recommended action:** Replace with Entra ID sign-in.
- **Severity:** Low
- **Disposition:** Defer

### I-09: Copilot's answers come from a small local model, so they can be wrong and take about 12 seconds

- **Description:** Free text goes to Llama 3.2 3B running on this computer's CPU through Ollama. Typical replies take 12 to 13 seconds, and a small model can state things that are not true. Questions about your own history, mentions, unread, and live data are answered by exact code, not by the model, and the model is told to say when it does not know.
- **Why it matters:** Users may trust a fluent but wrong answer, and a 12-second wait with no indicator feels slow.
- **Recommended action:** Show a "Copilot is typing" indicator, try a larger model with `CHATAPP_AI_MODEL` (for example `qwen2.5:7b`) or hardware acceleration, and for production use an approved hosted model after a data-protection review (risk R-21).
- **Severity:** Low
- **Disposition:** Defer

### I-10: Database calls run on the main event loop

- **Description:** Fine for 10 people. A slow query would pause every connection at higher load (risk R-17).
- **Why it matters:** A scaling limit, not a lab defect.
- **Recommended action:** Move to an async driver and a connection pool in production.
- **Severity:** Low
- **Disposition:** Defer

## Summary

| ID | Title | Severity | Disposition |
| --- | --- | --- | --- |
| I-01 | The web server's own log line printed the full session token | Medium | Done |
| I-02 | A deletion made in the same millisecond as a sync could be missed | Medium | Done |
| I-03 | The design documents said bots were out of scope | Medium | Done |
| I-04 | Live lookups send a place name to a free third-party service | Medium | Address |
| I-05 | The interface was checked by hand once, and accessibility was not audited | Medium | Address |
| I-06 | Copilot joining every group and replying to everything is on by default for everyone | Medium | Address |
| I-07 | The test specification does not list the assistant tests and numbers differ | Low | Defer |
| I-08 | The session token is kept in the browser's session storage | Low | Defer |
| I-09 | Copilot's answers come from a small local model, so they can be wrong and take about 12 seconds | Low | Defer |
| I-10 | Database calls run on the main event loop | Low | Defer |
