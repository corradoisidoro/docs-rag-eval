# Test questions for `acme-engineering-handbook.md`

Use with `POST /ask`. The handbook invents Acme-specific numbers, so a correct
answer shows retrieval worked. A model answering from general knowledge will
usually get these wrong.

## A. Single-fact lookups (should answer and cite the section)

| # | Question | Expected answer | Section |
|---|---|---|---|
| 1 | What is the maximum length of a function at Acme? | 40 lines (excluding blanks and comments) | 2.1 |
| 2 | How many approvals does a pull request need? | 2, one from a CODEOWNERS owner | 3.4 |
| 3 | What is the maximum pull request size before the bot warns? | 400 changed lines (blocked above 1,000) | 3.3 |
| 4 | What is the minimum overall test coverage? | 80% (domain layer 90%) | 4.2 |
| 5 | What is the default page size for list endpoints? | 25 (max 100) | 5.5 |
| 6 | How long do access tokens last? | 15 minutes (refresh tokens 7 days) | 7.2 |
| 7 | Which password hashing algorithm is required? | argon2id | 7.2 |
| 8 | What is the retry policy for transient failures? | 3 attempts, exponential backoff from 200 ms, ±20% jitter | 8.6 |
| 9 | When does the circuit breaker open? | When 50% of calls fail in a 30-second window (min 20 calls) | 8.7 |
| 10 | What is the recovery time objective for databases? | 1 hour (RPO 5 minutes) | 6.8 |
| 11 | How long must a SEV1 be acknowledged within? | 5 minutes | 13.1 |
| 12 | When are regular production deployments allowed? | Tuesday to Thursday, 10:00–16:00 CET | 11.4 |
| 13 | How long do on-call rotations last? | One week, Monday 10:00 to next Monday 10:00 | 13.5 |
| 14 | What is the p95 latency target? | Under 300 ms | 9.2 |
| 15 | How fast must a critical vulnerability be patched? | Within 48 hours | 7.7 |

## B. Questions needing wording variation (tests embeddings, not keywords)

| # | Question | Expected answer |
|---|---|---|
| 16 | How big can a file upload be by default? | 10 MB |
| 17 | What happens after 5 wrong login attempts? | Account locked for 15 minutes |
| 18 | How quickly must a leaked secret be replaced? | Within 1 hour (rotation otherwise every 90 days) |
| 19 | What database should I use for vector search? | PostgreSQL with pgvector |
| 20 | How should money be stored in the database? | Integers in the smallest currency unit plus currency code; no floats |
| 21 | What does a canary release do at Acme? | 5% of traffic for 30 minutes, then 25%, then 100% |
| 22 | How long should I keep a feature branch alive? | At most 3 working days |
| 23 | What do I do if a test is flaky? | Quarantine within 24 hours; fix or delete within 10 working days |
| 24 | After how many delivery attempts does a message go to the dead letter queue? | 5 |
| 25 | What is the Acme rule for naming Python constants? | `UPPER_SNAKE` |

## C. Multi-section questions (tests top_k and context assembly)

Try these with `top_k` 5 and 10 and compare.

| # | Question | What a good answer combines |
|---|---|---|
| 26 | What are all the places where Acme specifies 30 days or 30 seconds? | Secure coding course (30 days), bus-factor plan (30 days), erasure requests (30 days), statement timeout (30 s), circuit-breaker window/open state (30 s), medium vulnerabilities (30 days) |
| 27 | Summarise how Acme handles failures when calling another service. | Timeouts (5 s), retries (3 attempts, 200 ms backoff), circuit breaker, bulkheads, idempotency |
| 28 | What must be true before a task is considered done? | Merged, tested, documented, metrics/alerts, feature flag owner |
| 29 | What security rules apply to secrets and tokens? | Vault, gitleaks, 90-day rotation, 1-hour leak rotation, 15-minute JWTs |
| 30 | Describe the steps and rules of the deployment pipeline. | Stages 1–9, under 20 min, build once, windows, canary, rollback in 10 min |

## D. Should NOT be answerable (tests the relevance threshold)

The expected reply is "I could not find relevant information in the documents."
or a statement that the context does not contain the answer.

| # | Question | Why it should fail |
|---|---|---|
| 31 | What is Acme's vacation policy? | Not in the handbook |
| 32 | Who is the CEO of Acme? | Not in the handbook |
| 33 | What is the capital of France? | General knowledge, off-topic |
| 34 | How do I configure Kubernetes autoscaling at Acme? | Kubernetes is mentioned only for health checks |
| 35 | What is Acme's policy on using Rust in production? | Rust appears only in the memory section |

If #33–#35 return confident answers, raise `MIN_RELEVANCE_SCORE`. If #1–#15
return "could not find", lower it. A good value is the one where both groups
behave correctly.

## E. Quick curl checks (PowerShell)

```powershell
curl.exe -X POST http://<API_HOST>:<API_PORT>/ingest

curl.exe -X POST http://<API_HOST>:<API_PORT>/ask `
  -H "Content-Type: application/json" `
  -d '{\"question\": \"What is the maximum length of a function at Acme?\", \"top_k\": 5}'
```

Replace `<API_HOST>` and `<API_PORT>` with the values from `.env`.

## F. Re-ingestion checks

1. Run `/ingest` twice. The second call should report `documents_processed: 0`.
2. Change "40 lines" to "50 lines" in section 2.1, run `/ingest`, then ask question 1. It should answer 50.
3. Move the file out of `corpus/` and run `/ingest`. It should report `documents_deleted: 1`, and question 1 should no longer be answerable.
