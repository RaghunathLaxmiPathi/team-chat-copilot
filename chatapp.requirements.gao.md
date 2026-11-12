# Requirements Critique (GAO)

Date: 2026-11-11
Artifact reviewed: [chatapp.requirements.md](./chatapp.requirements.md)

> **Status at a glance**
> 9 findings: 0 High, 5 Medium, 4 Low. Disposition follows the fixed rule: Medium is Address and Low is Defer. No High findings were found. The 5 Medium findings have been applied to the requirements and are marked Done.

## Checks that came up clean

- **Fundamentals coverage:** each Fundamental has at least one requirement: quality (NFR-06), capacity (NFR-04), availability (NFR-01), resiliency (NFR-02, NFR-03), security (SEC-01 to SEC-08), privacy (PRV-01 to PRV-04), accessibility (ACC-01 to ACC-03), supportability (OPS-01 to OPS-05).
- **Traceability:** every requirement names an assumption.
- **Contradictions with the assumptions:** none found. The one inherited conflict (plain text only vs markdown, G-18) is flagged as an open item.

## Medium severity

### R-01: Latency SLO does not say what happens for offline recipients

- **Description:** SLO-02 measures server receive to the recipient client's confirmation. It does not say whether recipients who are offline are counted. It also does not say what happens when a client confirms late because of a slow device or network.
- **Why it matters:** If offline deliveries count, the SLO measures the user's connectivity, not the service. If they are silently dropped, nobody can tell. The test and the metric will each make a different guess.
- **Recommended action:** State that only deliveries to recipients with an open connection at send time are measured. Deliveries to offline users are covered by the catch-up requirement FR-45, not by SLO-02.
- **Severity:** Medium
- **Disposition:** Done

### R-02: "Does not answer" in the Success Rate SLO has no timeout

- **Description:** SLO-01 counts a request as failed if the service "does not answer", with no time limit. It also does not say whether the real-time connection (connect, resume) counts as a request.
- **Why it matters:** Without a timeout, slow requests are not failures, and the measurement can look healthy while users wait. Excluding the real-time connection leaves the core feature outside the SLO.
- **Recommended action:** Define a timeout (for example 10 seconds) after which a request is a failure. State that a failed real-time connection attempt or a resume that errors counts as a failed request.
- **Severity:** Medium
- **Disposition:** Done

### R-03: No minimum sample size for the percentiles and rates

- **Description:** The requirements note that the 1-hour window holds about 100 requests, but do not say what to report when there are too few samples. With 100 samples, P99 is one sample.
- **Why it matters:** The SLO endpoint can show a false breach or a false pass. People will stop trusting it.
- **Recommended action:** Require a minimum sample count per window (for example 100 for P99, 30 for P95). Below that, report "insufficient data" rather than a value.
- **Severity:** Medium
- **Disposition:** Done

### R-04: Re-added group members have no defined visibility

- **Description:** FR-15 says a person added to a group chat sees only messages sent after they joined. It does not cover a person who is removed and later re-added.
- **Why it matters:** The answer decides what a person can read after being removed, which is a privacy decision. Engineers will choose differently in different places.
- **Recommended action:** State that a re-added member sees messages from their original join point and messages after the re-add, but not those sent while removed.
- **Severity:** Medium
- **Disposition:** Done

### R-05: No session lifetime requirement

- **Description:** FR-01 and SEC-06 cover sign-in, but nothing says how long a signed-in session lasts or how it is renewed.
- **Why it matters:** A long-lived session on a shared or lost device exposes sensitive chats. FR-04 requires immediate access removal, which also depends on how sessions are checked.
- **Recommended action:** Add a requirement for a maximum session lifetime (for example 8 hours) and for the server to re-check that the user is still active on every request and real-time connection.
- **Severity:** Medium
- **Disposition:** Done

## Low severity

### R-06: Rate-limit refusals are invisible to the SLOs

- **Description:** FR-46 refusals return a 4xx response, which SLO-01 excludes. If the limit is set too low, real users are refused and no SLO shows it.
- **Why it matters:** A minor blind spot at this scale. The assumption (A-31) fixes the limit at 30 a minute, which is generous for 10 people.
- **Recommended action:** Track refusal counts as a metric. No requirement change needed now.
- **Severity:** Low
- **Disposition:** Defer

### R-07: The 10 times headroom in NFR-04 has no assumption behind it

- **Description:** NFR-04 asks for 10 times headroom. The assumptions give the load but no growth factor.
- **Why it matters:** It is a reasonable guess, but it is not traceable. Growth is an open question in the assumptions.
- **Recommended action:** Keep it as a proposal and confirm it when growth is answered.
- **Severity:** Low
- **Disposition:** Defer

### R-08: "Partial" is used in the Lab column but not defined

- **Description:** The legend defines Yes, Stub, and No. NFR-01 uses "Partial".
- **Why it matters:** Minor inconsistency in the document.
- **Recommended action:** Use "Stub" or add "Partial" to the legend.
- **Severity:** Low
- **Disposition:** Defer

### R-09: Small limits are missing

- **Description:** There is no limit on the number of attachments per message, on username format, or on search result size.
- **Why it matters:** These are small edge cases. Sensible defaults will do for now.
- **Recommended action:** Set defaults in the functional specs.
- **Severity:** Low
- **Disposition:** Defer

## Summary

| ID | Title | Severity | Disposition |
| --- | --- | --- | --- |
| R-01 | Latency SLO does not say what happens for offline recipients | Medium | Done |
| R-02 | "Does not answer" in the Success Rate SLO has no timeout | Medium | Done |
| R-03 | No minimum sample size for the percentiles and rates | Medium | Done |
| R-04 | Re-added group members have no defined visibility | Medium | Done |
| R-05 | No session lifetime requirement | Medium | Done |
| R-06 | Rate-limit refusals are invisible to the SLOs | Low | Defer |
| R-07 | The 10 times headroom in NFR-04 has no assumption behind it | Low | Defer |
| R-08 | "Partial" is used in the Lab column but not defined | Low | Defer |
| R-09 | Small limits are missing | Low | Defer |
