# Test Specifications Critique (GAO)

Date: 2026-11-11
Artifact reviewed: [chatapp.testspecs.md](./chatapp.testspecs.md)

> **Status at a glance**
> 6 findings: 0 High, 4 Medium, 2 Low. Disposition follows the fixed rule: Medium is Address and Low is Defer. The 4 Medium findings have been applied to the test specifications and are marked Done.

## Checks that came up clean

- **Requirement coverage:** every functional requirement, SLO, security, privacy, and supportability requirement that can be tested locally has at least one test. The ones that cannot are listed with a reason and a production test method (section 6).
- **Negative paths:** each protective rule (membership, deletion, deactivation, limits) has a refusal test.
- **Independence:** tests use a fresh service and database each, so order does not matter.

## Medium severity

### TS-01: Capacity headroom (NFR-04) had no test

- **Description:** NFR-04 asks for ten times headroom. No test pushed the service beyond the expected load.
- **Why it matters:** The headroom claim in the architecture was unverified.
- **Recommended action:** Add a test with 100 connections on one channel and 200 messages, checking order, closure, and latency.
- **Severity:** Medium
- **Disposition:** Done

### TS-02: Atomicity of a send was not tested

- **Description:** The design relies on one transaction for number, message, mentions, and attachment links. No test made a step fail and checked that nothing was left behind.
- **Why it matters:** A partial write could leave a gap in the numbers or an orphan mention, which breaks ordering and catch-up.
- **Recommended action:** Add a test that fails a step inside the transaction and checks for no partial data and no consumed number.
- **Severity:** Medium
- **Disposition:** Done

### TS-03: UTC time storage (FR-30) had no test

- **Description:** FR-30 requires times to be stored in UTC. No test checked it.
- **Why it matters:** Time zone mistakes are easy to introduce and hard to find.
- **Recommended action:** Add a test that checks the format and zone of all stored and returned times.
- **Severity:** Medium
- **Disposition:** Done

### TS-04: The log test would miss tokens in real-time addresses

- **Description:** The real-time connection carries the token in its address (risk R-12). A standard server access log would print that address. The log test only looked for message text.
- **Why it matters:** A token in a log is a credential leak.
- **Recommended action:** Extend the log test to check for tokens, including access lines for the real-time address.
- **Severity:** Medium
- **Disposition:** Done

## Low severity

### TS-05: The 10-second request limit is only tested in the tracker

- **Description:** T-61 tests that a slow request counts as a failure in the tracker. It does not test the middleware that measures the time.
- **Why it matters:** A bug in the middleware's timing would pass this test. The effect is small, because the middleware logic is a few lines.
- **Recommended action:** Add a deliberately slow test route when the middleware changes.
- **Severity:** Low
- **Disposition:** Defer

### TS-06: The concurrency test may not create true parallelism

- **Description:** T-12 uses the test client, which may serialize requests. It could pass without exercising overlapping writes.
- **Why it matters:** The service runs one writer on one event loop, so overlapping writes cannot happen in this design. The test mainly guards future changes.
- **Recommended action:** Add a multi-process test if the design ever allows more than one writer.
- **Severity:** Low
- **Disposition:** Defer

## Summary

| ID | Title | Severity | Disposition |
| --- | --- | --- | --- |
| TS-01 | Capacity headroom (NFR-04) had no test | Medium | Done |
| TS-02 | Atomicity of a send was not tested | Medium | Done |
| TS-03 | UTC time storage (FR-30) had no test | Medium | Done |
| TS-04 | The log test would miss tokens in real-time addresses | Medium | Done |
| TS-05 | The 10-second request limit is only tested in the tracker | Low | Defer |
| TS-06 | The concurrency test may not create true parallelism | Low | Defer |
