# Acme Engineering Handbook

Version 4.2 — maintained by the Platform Engineering Guild. This handbook describes how Acme builds, reviews, tests, ships and operates software. Where it states a number, the number is a rule, not a suggestion.

---

# Part 1: Principles

## 1.1 Why this handbook exists

Acme has about 140 engineers working across 23 services. Without shared conventions, every team reinvents the same decisions and every code review turns into an argument about taste. The handbook settles the common questions once so that reviews can focus on correctness and design.

The handbook is versioned. Changes are proposed through a pull request against the `engineering-handbook` repository and need approval from two Guild members. The current version is 4.2, released in March.

## 1.2 The five core principles

Acme engineering follows five principles, in priority order. When two principles conflict, the one listed first wins.

1. **Correctness before speed.** A fast wrong answer is worse than a slow right one.
2. **Readability over cleverness.** Code is read about ten times more often than it is written. We optimise for the reader.
3. **Small, reversible changes.** Prefer a change that can be rolled back in minutes over a large change that cannot.
4. **Make failure visible.** Errors must be logged, measured and alerted on. Silent failure is a defect.
5. **Automate the boring parts.** Formatting, linting, dependency updates and deployments are done by machines.

## 1.3 The "bus factor" rule

Every service must have at least three engineers who can deploy it, debug it and explain its architecture. A service with a bus factor below three is reported on the quarterly engineering health dashboard and the owning team must produce a knowledge-sharing plan within 30 days.

## 1.4 Definition of done

A task is done only when all of the following are true:

- The code is merged to the main branch.
- Automated tests cover the new behaviour.
- Documentation is updated, including the service README and any affected API specification.
- Metrics and alerts exist for any new failure mode.
- The feature flag, if any, has an owner and a removal date.

---

# Part 2: Coding Standards

## 2.1 General rules for all languages

- **Function length.** A function should not exceed 40 lines, excluding blank lines and comments. Longer functions must be split unless a Guild member approves an exception in the pull request.
- **Parameters.** A function takes at most 5 parameters. Beyond that, introduce a parameter object.
- **Nesting depth.** Maximum nesting depth is 3 levels of `if`, `for`, `while` or `try`. Use early returns and guard clauses to flatten code.
- **File length.** A source file should stay under 500 lines. When a file grows past 500 lines, treat it as a signal to split responsibilities.
- **Cyclomatic complexity.** The static analyser fails the build when any function exceeds a complexity of 10.
- **Comments.** Comments explain *why*, never *what*. If a comment restates the code, delete it or rename the code until the comment is unnecessary.
- **TODO comments.** A TODO must include a ticket reference, for example `# TODO(ACME-2291): remove after migration`. Bare TODOs fail the lint step.

## 2.2 Python standards

Acme uses Python 3.13 for new services and requires type hints on all public functions.

- **Formatter and linter.** We use `ruff` for both. The line length is 88 characters.
- **Type checking.** `mypy` runs in strict mode on all packages under `src/`.
- **Dependency management.** Use `uv` and commit the lock file. Never install packages with bare `pip` on a shared machine.
- **Imports.** Absolute imports only. Wildcard imports are forbidden.
- **Data containers.** Prefer `dataclass(frozen=True)` or Pydantic models over dictionaries for structured data.
- **Mutable defaults.** Never use a mutable default argument. Use `None` and create the value inside the function.

```python
# Bad: the list is shared between calls
def add_tag(tag, tags=[]):
    tags.append(tag)
    return tags


# Good
def add_tag(tag: str, tags: list[str] | None = None) -> list[str]:
    tags = [] if tags is None else tags
    return [*tags, tag]
```

- **Context managers.** Any resource that needs closing (files, connections, locks) must be used inside a `with` block.
- **Exceptions.** Catch the narrowest exception that makes sense. A bare `except:` is forbidden, and `except Exception:` requires a comment explaining why.

## 2.3 C# standards

Acme targets .NET 10 for new services.

- **Nullable reference types** are enabled in every project and warnings are treated as errors.
- **Async naming.** Methods returning `Task` end in `Async`, for example `GetOrderAsync`.
- **CancellationToken.** Every async method that performs I/O accepts a `CancellationToken` as its last parameter.
- **Records.** Use `record` types for immutable data transfer objects.
- **Dependency injection.** Constructor injection only. The service locator pattern is forbidden.
- **LINQ.** Keep LINQ chains to at most 5 operators. Longer chains should be split into named intermediate variables.
- **Minimal APIs** are preferred over controllers for new HTTP services with fewer than 20 endpoints.

```csharp
public async Task<Order?> GetOrderAsync(Guid id, CancellationToken ct)
{
    return await _db.Orders
        .AsNoTracking()
        .FirstOrDefaultAsync(o => o.Id == id, ct);
}
```

## 2.4 Go standards

- Code must pass `gofmt` and `go vet` with no findings. The `golangci-lint` configuration lives in the repository root.
- **Errors are values.** Wrap errors with context using `fmt.Errorf("load config: %w", err)`. Never discard an error with `_` unless a comment explains why.
- **Context.** The first parameter of any function that performs I/O is `ctx context.Context`.
- **Goroutines.** Every goroutine must have a clear owner and a way to stop. Use `errgroup` to manage groups of goroutines.
- **Interfaces** are defined by the consumer, not the producer, and should be small, ideally one to three methods.
- **Package names** are short, lowercase and singular. `user`, not `users` or `user_service`.

## 2.5 Naming conventions

| Element | Python | C# | Go |
|---|---|---|---|
| Variable | `snake_case` | `camelCase` | `camelCase` |
| Function / method | `snake_case` | `PascalCase` | `PascalCase` (exported) |
| Class / type | `PascalCase` | `PascalCase` | `PascalCase` |
| Constant | `UPPER_SNAKE` | `PascalCase` | `PascalCase` |
| Private member | `_leading_underscore` | `_camelCase` field | lowercase first letter |
| Boolean | `is_`, `has_`, `can_` prefix | `Is`, `Has`, `Can` prefix | `is`, `has` prefix |

General naming guidance:

- Names reveal intent. `elapsed_seconds` beats `t`.
- Avoid abbreviations except universally known ones such as `id`, `url`, `http`.
- Do not encode types in names. Use `users`, not `user_list`.
- Collections are plural, single items are singular.
- Boolean names read like a yes/no question: `is_active`, `has_permission`.

## 2.6 Code structure and design

### 2.6.1 The single responsibility rule

A module, class or function should have one reason to change. If you describe a class and need the word "and" more than once, it probably does too much.

### 2.6.2 Layering

Acme services use four layers. Dependencies point inward only.

1. **API layer** — HTTP routing, request validation, response mapping.
2. **Application layer** — use cases and orchestration.
3. **Domain layer** — business rules and entities. No framework imports allowed.
4. **Infrastructure layer** — databases, queues, external APIs.

The domain layer must not import from the infrastructure layer. An architecture test enforces this rule and fails the build on a violation.

### 2.6.3 Prefer composition over inheritance

Inheritance hierarchies deeper than 2 levels are rejected in review. Use interfaces (or protocols in Python) and composition instead.

### 2.6.4 Avoid premature abstraction

We follow the **rule of three**: do not extract a shared abstraction until the same pattern appears a third time. Two similar pieces of code are cheaper than the wrong abstraction.

---

# Part 3: Version Control and Code Review

## 3.1 Branching model

Acme uses **trunk-based development**. The `main` branch is always deployable. Developers create short-lived branches and merge them back quickly.

- Branches should live no longer than 3 working days.
- Branch names follow the pattern `type/TICKET-short-description`, for example `feature/ACME-1042-order-export` or `fix/ACME-1180-null-address`.
- Allowed types are `feature`, `fix`, `chore`, `docs` and `refactor`.
- Long-running branches are forbidden. Use feature flags to hide unfinished work instead.

## 3.2 Commit messages

Acme follows the **Conventional Commits** format:

```
type(scope): short summary in the imperative mood

Optional body explaining what and why.

Refs: ACME-1042
```

- The summary line is at most 72 characters.
- Use the imperative mood: "add retry logic", not "added retry logic".
- Allowed types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`, `ci`.
- A breaking change adds `!` after the type, for example `feat(api)!: remove v1 orders endpoint`, and includes a `BREAKING CHANGE:` footer.

## 3.3 Pull requests

- **Size.** A pull request should change at most 400 lines, excluding generated files and lock files. Larger changes must be split. The review bot posts a warning above 400 lines and blocks merge above 1,000 lines.
- **Description.** Every pull request uses the template: summary, motivation, testing done, rollout plan and rollback plan.
- **Draft pull requests** are encouraged for early feedback.
- **Self-review.** The author reads their own diff before requesting review.

## 3.4 Review rules

- Every pull request needs **2 approvals**, and at least one must come from an owner of the code listed in the `CODEOWNERS` file.
- Reviewers respond within **1 business day**. A pull request waiting more than 2 business days is escalated to the team lead.
- The author may not merge their own pull request without the required approvals, even when they have admin rights.
- All conversations must be resolved before merging.
- CI must be green. Flaky tests are fixed, not retried until they pass.

### 3.4.1 What reviewers look for

1. Does it do what the ticket asks?
2. Is it correct, including edge cases and failure paths?
3. Is it tested?
4. Is it readable and consistent with this handbook?
5. Does it introduce security, performance or operational risk?

Reviewers prefix comments to signal severity:

- `blocker:` must be fixed before merge.
- `suggestion:` worth considering, not required.
- `nit:` tiny style point, never blocks.
- `question:` the reviewer wants to understand.

### 3.4.2 Giving feedback

Comment on the code, not the person. Ask questions instead of issuing orders. Explain the reason behind a request. Praise good solutions out loud, since review should also teach.

## 3.5 Merge strategy

Pull requests are merged using **squash merge**. The squash commit message follows Conventional Commits and includes the pull request number. Merge commits and rebase merges are disabled on `main`.

## 3.6 Protected branches and tags

- `main` is protected. Direct pushes are blocked for everyone.
- Release tags use semantic versioning with a `v` prefix, for example `v2.14.0`.
- Tags are created by the release pipeline, never by hand.

---

# Part 4: Testing

## 4.1 The testing pyramid

Acme aims for roughly 70% unit tests, 20% integration tests and 10% end-to-end tests. If the ratio drifts, the testing guild raises it at the quarterly health review.

## 4.2 Coverage requirements

- Overall line coverage must be at least **80%** for every service.
- The domain layer must reach at least **90%** coverage.
- Coverage may not decrease in a pull request by more than 1 percentage point.
- Coverage is a floor, not a goal. A test that asserts nothing does not count, and the mutation testing job flags such tests.

## 4.3 Unit tests

- A unit test runs in under **100 milliseconds**. Tests slower than that are labelled integration tests.
- Unit tests do not touch the network, the file system or a real database.
- Follow the **Arrange–Act–Assert** structure and keep one logical assertion per test.
- Name tests after behaviour: `test_expired_token_is_rejected`, not `test_token_1`.
- Tests must be independent and runnable in any order.

```python
def test_discount_is_capped_at_fifty_percent():
    # Arrange
    order = make_order(total=Decimal("200.00"), discount_percent=80)
    # Act
    price = calculate_final_price(order)
    # Assert
    assert price == Decimal("100.00")
```

## 4.4 Test doubles

- Use **fakes** for in-memory implementations of repositories and queues.
- Use **stubs** to return canned data.
- Use **mocks** sparingly, only to verify an interaction that matters, such as "an email was sent once".
- Do not mock types you do not own. Wrap third-party libraries behind an interface you control and mock that instead.

## 4.5 Integration tests

Integration tests run against real dependencies started with Docker Compose through **Testcontainers**. Each test class gets a fresh database schema. Integration tests must finish within **5 minutes** in total for a single service.

## 4.6 End-to-end tests

End-to-end tests cover only critical user journeys: sign-up, checkout and password reset. There are at most 25 end-to-end tests per product. They run after deployment to the staging environment and block promotion to production on failure.

## 4.7 Property-based and mutation testing

- Use property-based testing (Hypothesis in Python, FsCheck in .NET) for parsers, serialisers and pricing rules.
- The mutation testing job runs weekly. A mutation score below **65%** on the domain layer opens an automatic ticket.

## 4.8 Flaky tests

A test that fails intermittently is quarantined within 24 hours and gets a ticket labelled `flaky`. A quarantined test must be fixed or deleted within 10 working days.

## 4.9 Test data

Never use production data in tests. Use factories or builders to create test objects. Personal data in fixtures must be obviously fake, such as `jane.doe@example.test`.

---

# Part 5: API Design

## 5.1 REST conventions

- Resource names are plural nouns in kebab-case: `/order-items`, not `/getOrderItem`.
- Use HTTP methods correctly: `GET` reads, `POST` creates, `PUT` replaces, `PATCH` partially updates, `DELETE` removes.
- `GET` requests never change state.
- Nested resources go at most **2 levels deep**: `/customers/42/orders` is fine, `/customers/42/orders/7/items/3/notes` is not.
- Use `snake_case` for JSON field names.

## 5.2 Versioning

APIs are versioned in the URL path: `/v1/orders`. A new major version is created only for breaking changes. Old versions are supported for at least **12 months** after the successor is released, and the `Sunset` header announces the removal date.

Additive changes (new optional fields, new endpoints) are not breaking and do not need a new version.

## 5.3 Status codes

| Code | Use |
|---|---|
| 200 | Successful read or update |
| 201 | Resource created, with a `Location` header |
| 204 | Success with no body, such as a delete |
| 400 | Malformed request |
| 401 | Missing or invalid authentication |
| 403 | Authenticated but not allowed |
| 404 | Resource does not exist |
| 409 | Conflict, such as a duplicate or version mismatch |
| 422 | Valid syntax but failed validation |
| 429 | Rate limit exceeded |
| 500 | Unexpected server error |
| 503 | Dependency unavailable, with `Retry-After` |

## 5.4 Error format

All errors use the RFC 9457 "problem details" format:

```json
{
  "type": "https://errors.acme.example/validation-failed",
  "title": "Validation failed",
  "status": 422,
  "detail": "The field 'quantity' must be greater than zero.",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736"
}
```

Every error response includes the `trace_id` so that support can find the matching logs. Error messages never leak stack traces, SQL or internal hostnames.

## 5.5 Pagination

- List endpoints use cursor-based pagination.
- The default page size is **25** items and the maximum is **100**. Requests above 100 are clamped to 100.
- Responses include `next_cursor`, which is `null` on the last page.
- Offset pagination is allowed only for small, static datasets of fewer than 10,000 rows.

## 5.6 Idempotency

`POST` endpoints that create money-affecting resources, such as payments and orders, must accept an `Idempotency-Key` header. The server stores the response for **24 hours** and returns the stored response when the same key is sent again.

## 5.7 Rate limiting

- Public endpoints allow **100 requests per minute** per API key.
- Authentication endpoints allow **10 requests per minute** per IP address.
- Exceeding the limit returns `429` with a `Retry-After` header.

## 5.8 Documentation

Every API has an OpenAPI 3.1 specification checked into the repository. The specification is validated in CI, and contract tests ensure the implementation matches it.

---

# Part 6: Databases and Data Access

## 6.1 Choosing a datastore

Acme's default relational database is **PostgreSQL 17**. Teams must justify any other choice in an architecture decision record.

| Need | Default choice |
|---|---|
| Transactional data | PostgreSQL |
| Caching and short-lived state | Redis |
| Full-text search | OpenSearch |
| Vector similarity search | PostgreSQL with `pgvector` |
| Analytics | The central data warehouse |
| Files and blobs | Object storage |

## 6.2 Schema design

- Table names are plural `snake_case`: `order_items`.
- Every table has a primary key. Acme prefers **UUID version 7** keys because they are time-ordered and index-friendly.
- Every table has `created_at` and `updated_at` columns of type `timestamptz`. All timestamps are stored in **UTC**.
- Monetary amounts are stored as integers in the smallest currency unit (cents) together with a three-letter currency code. Floating point types are forbidden for money.
- Soft deletes use a `deleted_at` column and a partial index that excludes deleted rows.
- Foreign keys are declared in the database, not just in application code.

## 6.3 Migrations

- Schema changes are made only through versioned migration scripts, never by hand.
- Migration files are named `V{timestamp}__{description}.sql`, for example `V20260310_1430__add_order_status.sql`.
- Migrations must be **backward compatible** with the previous application version, because deployments are rolling.
- Destructive changes follow the **expand and contract** pattern in three releases: add the new column, migrate readers and writers, then remove the old column.
- A migration that locks a large table for more than **5 seconds** in staging is rejected. Use `CREATE INDEX CONCURRENTLY` for large tables.

## 6.4 Indexing

- Every foreign key column is indexed unless a reviewer agrees otherwise.
- Create an index only for a query you can name. Unused indexes cost writes and storage.
- Use `EXPLAIN (ANALYZE, BUFFERS)` to verify that a new query uses the intended index.
- Review unused indexes every quarter using the `pg_stat_user_indexes` view.

## 6.5 Query rules

- Never build SQL by string concatenation. Use parameterised queries or an ORM.
- Avoid `SELECT *` in application code. List the columns you need.
- Beware the **N+1 query problem**: loading a list and then querying once per item. Use joins or batched loading.
- Queries that take longer than **200 milliseconds** at the 95th percentile are reported weekly to the owning team.
- Set a statement timeout of **30 seconds** on application connections.

```sql
-- Bad: N+1 pattern issues one query per order
SELECT * FROM orders WHERE customer_id = $1;
-- then, for each order:
SELECT * FROM order_items WHERE order_id = $2;

-- Good: one query with a join
SELECT o.id, o.total_cents, i.sku, i.quantity
FROM orders o
JOIN order_items i ON i.order_id = o.id
WHERE o.customer_id = $1;
```

## 6.6 Transactions

- Keep transactions short. A transaction must not wait on a network call to another service.
- Default isolation level is `READ COMMITTED`. Use `SERIALIZABLE` only with a documented reason and a retry loop.
- Use **optimistic concurrency** with a `version` column for entities edited by humans.
- For cross-service consistency use the **outbox pattern**: write the event to an `outbox` table in the same transaction as the state change, and a relay publishes it.

## 6.7 Connection pooling

The default application pool size is **20 connections** per instance, with a maximum of 40 under burst. The total across all instances must stay below 80% of the database's `max_connections`. Use PgBouncer in transaction mode for services with more than 10 instances.

## 6.8 Backups and recovery

- Production databases are backed up continuously with point-in-time recovery for **14 days**.
- Daily snapshots are retained for **35 days**.
- A restore drill runs every quarter. The recovery time objective (RTO) is **1 hour** and the recovery point objective (RPO) is **5 minutes**.

## 6.9 Caching

- Cache only data that is read far more often than it changes.
- Every cache entry has a TTL. The default TTL is **5 minutes**.
- Prefer **cache-aside**: read from the cache, fall back to the database and populate the cache.
- Prevent cache stampedes with request coalescing or a short lock.
- Never use the cache as the source of truth.

---

# Part 7: Security

## 7.1 Security mindset

Security is everyone's job. Every engineer completes the secure coding course within their first **30 days** and renews it every year.

## 7.2 Authentication and sessions

- Passwords are hashed with **argon2id**. MD5, SHA-1 and unsalted hashes are forbidden.
- Access tokens are JWTs that expire after **15 minutes**. Refresh tokens expire after **7 days** and are rotated on every use.
- Multi-factor authentication is mandatory for all staff accounts and for customer accounts with administrative rights.
- After **5 failed login attempts** within 10 minutes the account is locked for 15 minutes.
- Session cookies are `HttpOnly`, `Secure` and `SameSite=Lax`.

## 7.3 Authorisation

- Check authorisation on the server for every request. Hiding a button is not access control.
- Follow the **principle of least privilege**: grant the minimum permissions needed.
- Use role-based access control with named roles, and keep role definitions in code.
- Verify object ownership on every access, to prevent insecure direct object reference (IDOR) bugs.

## 7.4 Secrets management

- Secrets never appear in source code, logs, container images or chat messages.
- Secrets live in the central vault and are injected at runtime.
- The pre-commit hook and the CI pipeline run `gitleaks` and block commits containing secrets.
- Secrets are rotated at least every **90 days**. A leaked secret is rotated within **1 hour** of discovery.

## 7.5 Input validation and output encoding

- Validate all external input for type, length, range and format, preferably with an allow-list.
- Encode output for the context it is placed in (HTML, URL, SQL, shell).
- Avoid building shell commands from user input. When unavoidable, pass arguments as a list, never as one string.
- Limit upload size to **10 MB** by default and verify the real content type, not just the file extension.

## 7.6 The OWASP Top 10 at Acme

Reviewers keep the following risks in mind:

1. **Broken access control** — missing ownership checks.
2. **Cryptographic failures** — weak algorithms, missing TLS.
3. **Injection** — SQL, command and template injection.
4. **Insecure design** — missing threat modelling.
5. **Security misconfiguration** — default passwords, open buckets.
6. **Vulnerable components** — outdated dependencies.
7. **Authentication failures** — weak sessions, credential stuffing.
8. **Integrity failures** — unsigned updates, unsafe deserialisation.
9. **Logging failures** — missing audit trails.
10. **Server-side request forgery (SSRF)** — fetching attacker-chosen URLs.

## 7.7 Dependencies and supply chain

- Dependabot opens update pull requests weekly.
- A dependency with a **critical** vulnerability must be patched within **48 hours**, a **high** one within **7 days**, and a **medium** one within **30 days**.
- Every build produces a software bill of materials (SBOM).
- New third-party libraries need a licence check. Only MIT, Apache-2.0, BSD and ISC licences are pre-approved.
- Container base images come from the internal registry and are rebuilt weekly.

## 7.8 Encryption

- All traffic uses **TLS 1.3**. TLS 1.1 and lower are disabled.
- Data at rest is encrypted with AES-256.
- Personal data fields such as national identifiers are additionally encrypted at the application level.

## 7.9 Personal data and privacy

- Collect only the data you need.
- Personal data is deleted or anonymised **30 days** after a verified erasure request.
- Never write personal data, tokens or passwords to logs. Mask email addresses as `j***@example.com`.
- Production data may not be copied to developer machines.

## 7.10 Threat modelling

New services and major changes need a threat model using the **STRIDE** categories: Spoofing, Tampering, Repudiation, Information disclosure, Denial of service and Elevation of privilege. The model is reviewed by a security champion and stored next to the code.

---

# Part 8: Concurrency and Asynchronous Programming

## 8.1 Concurrency versus parallelism

**Concurrency** is dealing with many things at once, such as handling thousands of network connections. **Parallelism** is doing many things at the same time, such as using several CPU cores. Asynchronous code gives concurrency, while threads or processes can give parallelism.

## 8.2 Choosing a model

| Workload | Recommended approach |
|---|---|
| Many network calls (I/O bound) | `async`/`await` |
| Heavy computation (CPU bound) | Process pool or separate worker service |
| Blocking legacy library | Thread pool with a bounded size |
| Background jobs | Queue with workers |

## 8.3 Async rules

- Never block inside an async function. A synchronous `time.sleep` or `.Result` on a task can freeze the whole event loop.
- Do not fire and forget tasks. Always keep a reference and observe the result or the exception.
- Set a timeout on every outgoing call. The default timeout is **5 seconds** for service-to-service calls and **30 seconds** for calls to external partners.
- Support cancellation. When a user disconnects, abandon the work.

```python
import asyncio
import httpx


async def fetch_all(urls: list[str]) -> list[str]:
    async with httpx.AsyncClient(timeout=5.0) as client:
        responses = await asyncio.gather(*(client.get(u) for u in urls))
    return [r.text for r in responses]
```

## 8.4 Shared state and locks

- Prefer **immutable data** and message passing over shared mutable state.
- If you need a lock, hold it for the shortest time and never call unknown code while holding it.
- Always acquire multiple locks in the same global order to avoid **deadlocks**.
- A **race condition** happens when the result depends on timing. A check-then-act sequence (`if not exists: create`) must be made atomic with a lock, a unique constraint or a transaction.

## 8.5 The four conditions for deadlock

A deadlock needs all four of these: mutual exclusion, hold and wait, no preemption and circular wait. Breaking any one of them prevents deadlock. Acme's usual fix is to break circular wait by ordering lock acquisition.

## 8.6 Retries and backoff

Transient failures are normal in distributed systems. The Acme retry policy is:

- **3 attempts** in total (one initial call and two retries).
- **Exponential backoff** with a base delay of **200 ms**, doubling each time: 200 ms, then 400 ms.
- **Jitter** of plus or minus **20%** to avoid synchronised retry storms.
- Retry only idempotent operations, or operations that carry an idempotency key.
- Retry only on timeouts, connection errors and status codes 502, 503 and 504. Never retry a 4xx error.

```python
import random
import time


def call_with_retry(fn, attempts: int = 3, base_delay: float = 0.2):
    for attempt in range(attempts):
        try:
            return fn()
        except TransientError:
            if attempt == attempts - 1:
                raise
            delay = base_delay * (2**attempt)
            time.sleep(delay * random.uniform(0.8, 1.2))
```

## 8.7 Circuit breakers

A circuit breaker stops calling a failing dependency to give it time to recover. Acme's standard configuration:

- **Closed** state: calls pass through.
- The breaker **opens** when **50%** of calls fail within a 30-second window, with a minimum of 20 calls.
- **Open** state lasts **30 seconds** and fails fast.
- **Half-open** state lets 5 trial calls through. If they succeed, the breaker closes.

## 8.8 Bulkheads and backpressure

- Use **bulkheads** to isolate resources so that one slow dependency cannot exhaust the whole thread or connection pool.
- Apply **backpressure**: bounded queues that reject or slow producers when consumers fall behind. Unbounded queues are forbidden because they turn overload into out-of-memory crashes.

## 8.9 Message queues

- Delivery is **at least once**, so consumers must be idempotent.
- Failed messages are retried and then sent to a **dead letter queue** after **5 delivery attempts**.
- Messages carry a correlation id and a schema version.
- Alert when the oldest message in a queue is older than **10 minutes**.

---

# Part 9: Performance

## 9.1 Measure first

Never optimise without measurement. Profile first, change one thing, measure again. Premature optimisation wastes time and harms readability.

## 9.2 Service level objectives

| Metric | Target |
|---|---|
| Availability | 99.9% monthly (about 43 minutes of downtime) |
| API latency p50 | under 100 ms |
| API latency p95 | under 300 ms |
| API latency p99 | under 800 ms |
| Error rate | under 0.1% of requests |

The **error budget** is the allowed unreliability. When a service has used more than **100%** of its monthly error budget, feature work pauses and the team focuses on reliability until the budget recovers.

## 9.3 Algorithmic complexity

Understand Big-O notation. Common complexities from best to worst: constant O(1), logarithmic O(log n), linear O(n), linearithmic O(n log n), quadratic O(n²) and exponential O(2ⁿ).

- Looking up a key in a hash map is O(1) on average.
- Binary search on a sorted array is O(log n).
- Good general-purpose sorting is O(n log n).
- Nested loops over the same collection are usually O(n²) and deserve scrutiny on large inputs.

```python
# O(n^2): checks the list for every item
def has_duplicates_slow(items):
    return any(
        items[i] == items[j]
        for i in range(len(items))
        for j in range(i + 1, len(items))
    )


# O(n): uses a set
def has_duplicates_fast(items):
    return len(set(items)) != len(items)
```

## 9.4 Common performance problems

1. **N+1 queries** (see Part 6).
2. **Missing indexes** causing full table scans.
3. **Chatty services** making many small calls instead of one batch call.
4. **Large payloads**. Compress responses above **1 KB** with gzip or brotli.
5. **Synchronous work in the request path** that could be queued.
6. **Memory leaks** from unbounded caches or retained references.
7. **Excessive logging** in hot loops.

## 9.5 Load testing

- Load tests run with **k6** before any major release.
- The test must sustain **2 times** the peak production traffic of the last 90 days for 15 minutes without breaching the latency objectives.
- Soak tests run for 8 hours to find memory leaks.

## 9.6 Frontend performance

- Largest Contentful Paint should stay under **2.5 seconds**.
- Total JavaScript on the first page load should be under **250 KB** compressed.
- Serve static assets from the CDN with long cache lifetimes and content-hashed file names.

---

# Part 10: Error Handling, Logging and Observability

## 10.1 Error handling principles

- **Fail fast** on programmer errors, and **fail gracefully** on expected runtime errors.
- Distinguish **expected errors** (validation failure, not found) from **unexpected errors** (bugs, outages).
- Never swallow exceptions. If you catch an error, either handle it, add context and rethrow, or log it with a reason.
- Do not use exceptions for normal control flow.
- At service boundaries translate internal errors into the standard problem-details format.

## 10.2 Structured logging

- Logs are JSON, one event per line.
- Required fields: `timestamp` (UTC, ISO 8601), `level`, `service`, `message`, `trace_id` and `environment`.
- Log levels:
  - `DEBUG` — detailed diagnostics, disabled in production by default.
  - `INFO` — normal significant events.
  - `WARNING` — something unexpected that the system handled.
  - `ERROR` — an operation failed.
  - `CRITICAL` — the service cannot continue.
- Each log message should answer who, what and why without needing the code.
- Log retention is **30 days** hot and **1 year** archived.

## 10.3 The three pillars of observability

1. **Logs** — discrete events.
2. **Metrics** — numeric time series.
3. **Traces** — the path of a request across services.

Acme uses **OpenTelemetry** for all three. Every incoming request receives a trace id that is propagated through headers and included in logs.

## 10.4 Metrics

Follow the **RED method** for services: **R**ate, **E**rrors and **D**uration. Follow the **USE method** for resources: **U**tilisation, **S**aturation and **E**rrors.

Every service exposes the standard dashboard with request rate, error rate, latency percentiles, CPU, memory and dependency health.

## 10.5 Alerting

- Alert on **symptoms** that affect users, not on every cause.
- Every alert must be **actionable** and link to a runbook.
- Alerts that fire without needing action for 3 consecutive weeks are tuned or deleted.
- Paging alerts are reserved for situations needing a human within minutes. Everything else becomes a ticket.

## 10.6 Health checks

Services expose `/health/live` (the process is running) and `/health/ready` (it can serve traffic, including dependencies). Kubernetes uses these for restarts and traffic routing.

---

# Part 11: CI/CD and Deployment

## 11.1 Pipeline stages

Every service uses the standard pipeline, which runs on each pull request and on `main`:

1. **Lint and format** — `ruff`, `dotnet format` or `golangci-lint`.
2. **Type check** — `mypy`, the C# compiler with warnings as errors, or `go vet`.
3. **Unit tests** — must finish in under **3 minutes**.
4. **Security scan** — `gitleaks`, dependency audit and container scan.
5. **Build** — a single immutable container image tagged with the commit SHA.
6. **Integration tests** — using Testcontainers.
7. **Deploy to staging** — automatic on merge to `main`.
8. **End-to-end tests** — against staging.
9. **Deploy to production** — one click or automatic, depending on the service tier.

The full pipeline should complete in under **20 minutes**. A pipeline that regularly exceeds this is a priority for the owning team.

## 11.2 Build once, deploy many

The same image that passed tests in staging is promoted to production. Never rebuild for production. Configuration differences come from environment variables and the vault, never from the image.

## 11.3 Environments

| Environment | Purpose | Data |
|---|---|---|
| `dev` | Developer experiments | Synthetic |
| `staging` | Production-like verification | Anonymised or synthetic |
| `production` | Real customers | Real |

Staging must match production in topology and versions. Differences are documented.

## 11.4 Deployment windows

- Regular production deployments happen **Tuesday to Thursday between 10:00 and 16:00 CET**.
- There is a **change freeze** on Fridays, weekends, public holidays and from 15 December to 5 January.
- Emergency fixes may deploy at any time with approval from the on-call lead.

## 11.5 Deployment strategies

- **Rolling deployment** is the default. Instances are replaced gradually and health checks gate each step.
- **Canary release** is used for high-risk changes. Route **5%** of traffic to the new version for 30 minutes, then 25%, then 100%, while watching error rate and latency.
- **Blue-green** deployment is used for databases-adjacent changes needing instant switch-back.
- **Feature flags** decouple deployment from release. Each flag has an owner and a removal date, and flags older than **90 days** are reported.

## 11.6 Rollback

- Every deployment must be reversible. A rollback to the previous version must complete within **10 minutes**.
- The pipeline rolls back automatically if the error rate rises above **2%** or p95 latency doubles during the canary phase.
- Database migrations are backward compatible so that rollback does not require reverting the schema.

## 11.7 Infrastructure as code

- All infrastructure is defined with Terraform and stored in version control.
- Manual changes in the cloud console are forbidden in production. Drift is detected nightly and reported.
- Terraform state is stored remotely with locking.

## 11.8 Containers

- Images are built from small base images such as `distroless` or `alpine`.
- Containers run as a **non-root user**.
- One process per container.
- Images carry labels for the commit SHA, build time and owning team.
- Set CPU and memory requests and limits for every container.

## 11.9 Twelve-factor guidance

Acme services follow the twelve-factor app approach. The most important points are: store configuration in the environment, treat backing services as attached resources, keep processes stateless, export services via port binding, treat logs as event streams and keep development and production as similar as possible.

---

# Part 12: Architecture

## 12.1 Monolith or microservices

Start with a **modular monolith** unless there is a clear need to split. A microservice must justify itself with at least one of the following:

- It must scale independently.
- It is owned by a separate team with its own release cadence.
- It needs a different technology or reliability profile.
- It isolates a security or compliance boundary.

Splitting too early creates a distributed monolith with all the costs of networking and none of the benefits.

## 12.2 Architecture decision records

Significant decisions are recorded as **architecture decision records** (ADRs) in the `docs/adr/` folder. An ADR has these sections: context, decision, alternatives considered and consequences. ADRs are numbered, for example `ADR-0042-use-postgres-for-orders.md`, and are never deleted. A superseded ADR is marked as such and points to its replacement.

## 12.3 Communication styles

| Style | Use when | Example |
|---|---|---|
| Synchronous HTTP | The caller needs an immediate answer | Fetch a price |
| Asynchronous events | Work can happen later or many consumers react | `OrderPlaced` |
| Batch | Large volumes, no urgency | Nightly reports |

Prefer asynchronous events for integration between bounded contexts, because they reduce coupling and temporal dependency.

## 12.4 Domain-driven design

- Use **bounded contexts** to separate models. The word "customer" may mean different things in billing and shipping.
- Use an **aggregate** as a consistency boundary. A transaction should change only one aggregate.
- Use **value objects** for concepts defined by their values, such as `Money` or `EmailAddress`.
- Maintain a **ubiquitous language** shared between engineers and business people.

## 12.5 Common patterns

- **Repository** — abstracts persistence behind a collection-like interface.
- **Strategy** — swaps algorithms behind a common interface.
- **Factory** — centralises object creation.
- **Observer** — notifies subscribers about changes.
- **Adapter** — wraps an incompatible interface.
- **Saga** — coordinates a long-running transaction across services with compensating actions.
- **CQRS** — separates the write model from the read model. Use it only when read and write needs differ substantially.
- **Strangler fig** — gradually replaces a legacy system by routing functionality piece by piece.

## 12.6 SOLID principles

1. **Single responsibility** — one reason to change.
2. **Open/closed** — open for extension, closed for modification.
3. **Liskov substitution** — subtypes must be usable wherever their base type is expected.
4. **Interface segregation** — many small interfaces beat one large one.
5. **Dependency inversion** — depend on abstractions, not concrete implementations.

## 12.7 CAP theorem and consistency

The **CAP theorem** states that during a network partition a distributed system must choose between consistency and availability. Acme chooses **consistency** for payments and inventory, and **availability** for product browsing and recommendations. Systems that favour availability use **eventual consistency**, so clients must tolerate slightly stale data.

## 12.8 Technical debt

- Debt is tracked as tickets with the label `tech-debt`.
- Each team reserves **20%** of every sprint's capacity for debt reduction and maintenance.
- Debt is taken deliberately and recorded, not accidentally accumulated. When shipping a shortcut, create the ticket in the same pull request.

---

# Part 13: Incident Management and On-Call

## 13.1 Severity levels

| Severity | Definition | Acknowledge within | Update cadence |
|---|---|---|---|
| **SEV1** | Complete outage or data loss affecting many customers | **5 minutes** | every 15 minutes |
| **SEV2** | Major feature degraded, workaround exists | **15 minutes** | every 30 minutes |
| **SEV3** | Minor issue, limited impact | next business day | as needed |

## 13.2 Roles during an incident

- **Incident commander** — coordinates, makes decisions and keeps the timeline.
- **Communications lead** — updates the status page and stakeholders.
- **Operations lead** — investigates and applies fixes.
- **Scribe** — records events in the incident channel.

For a SEV1 all four roles are filled. The first responder acts as incident commander until relieved.

## 13.3 Response steps

1. **Acknowledge** the page.
2. **Assess** impact and assign a severity.
3. **Communicate** on the status page within **10 minutes** for SEV1.
4. **Mitigate** first. Restore service by rolling back, failing over or disabling a feature flag before searching for the root cause.
5. **Resolve** and confirm with metrics.
6. **Review** with a postmortem.

## 13.4 Postmortems

- Postmortems are **blameless**. They examine systems and processes, not individuals.
- A postmortem is required for every SEV1 and SEV2 and is published within **5 business days**.
- The document includes: summary, impact, timeline, root cause, what went well, what went poorly and action items with owners and due dates.
- A common technique is the **five whys**: keep asking why until a systemic cause appears.
- Action items are tracked to completion, and overdue items are reviewed monthly.

## 13.5 On-call rotation

- On-call rotations last **one week**, from Monday 10:00 to the following Monday 10:00.
- A rotation has a primary and a secondary engineer.
- A team needs at least **5 engineers** in its rotation. Smaller teams join a shared rotation.
- On-call engineers receive a stipend and compensatory time off after a night with more than 2 pages.
- If the primary does not acknowledge within **10 minutes**, the page escalates to the secondary, and then to the team lead.
- Handover happens in a short meeting every Monday where open issues and risky changes are discussed.

## 13.6 Runbooks

Each alert links to a runbook containing: what the alert means, how to confirm impact, likely causes, step-by-step mitigation and who to escalate to. Runbooks are tested in game days twice a year.

---

# Part 14: Fundamentals Reference

## 14.1 Data structures at a glance

| Structure | Access | Search | Insert | Notes |
|---|---|---|---|---|
| Array | O(1) | O(n) | O(n) | Contiguous memory, cache friendly |
| Linked list | O(n) | O(n) | O(1) at known node | Poor cache behaviour |
| Hash map | O(1) avg | O(1) avg | O(1) avg | Unordered, needs a good hash |
| Binary search tree (balanced) | O(log n) | O(log n) | O(log n) | Ordered iteration |
| Heap | O(1) top | O(n) | O(log n) | Priority queues |
| Stack | — | — | O(1) | Last in, first out |
| Queue | — | — | O(1) | First in, first out |

## 14.2 Algorithms worth knowing

- **Binary search** finds an element in a sorted array in O(log n).
- **Merge sort** is stable and runs in O(n log n) time with O(n) extra space.
- **Quicksort** averages O(n log n) but degrades to O(n²) on bad pivots.
- **Breadth-first search** explores a graph level by level and finds shortest paths in unweighted graphs.
- **Depth-first search** explores as deep as possible first and is natural for recursion and topological sorting.
- **Dijkstra's algorithm** finds shortest paths in graphs with non-negative edge weights.
- **Dynamic programming** solves overlapping subproblems once and caches results.

```python
def binary_search(items: list[int], target: int) -> int:
    low, high = 0, len(items) - 1
    while low <= high:
        mid = (low + high) // 2
        if items[mid] == target:
            return mid
        if items[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1
```

## 14.3 Recursion

A recursive function needs a **base case** and a step that moves toward it. Without a base case it recurses forever and overflows the stack. Deep recursion on large inputs should be rewritten as a loop or use an explicit stack.

## 14.4 Memory management

- The **stack** holds local variables and call frames and is fast but small.
- The **heap** holds dynamically allocated objects and is larger but slower.
- Languages such as Python, C# and Go use **garbage collection**. Rust uses ownership and borrowing to free memory deterministically without a collector.
- A **memory leak** in a garbage-collected language usually means objects are still referenced, for example by a growing cache or an unremoved event handler.

## 14.5 Networking basics

- **TCP** gives reliable, ordered delivery. **UDP** is connectionless and lossy but low latency.
- **HTTP/2** multiplexes requests over one connection. **HTTP/3** runs over QUIC.
- **DNS** maps names to addresses and is cached according to TTL values.
- A **load balancer** distributes requests across instances using algorithms such as round robin or least connections.

## 14.6 Floating point warning

Binary floating point cannot represent most decimal fractions exactly, so `0.1 + 0.2` is not exactly `0.3`. Never compare floats with `==` and never store money as a float. Use integers of the smallest unit or a decimal type.

## 14.7 Time and dates

- Store and transmit timestamps in **UTC** using ISO 8601, for example `2026-03-10T14:30:00Z`.
- Convert to local time zones only at the presentation layer.
- Never assume a day has 24 hours, because of daylight saving transitions.
- Use library types such as `datetime` with time zones, `DateTimeOffset` or `time.Time`, never hand-rolled arithmetic.

---

# Part 15: Glossary

- **ADR** — architecture decision record, a short document capturing a design decision.
- **Backpressure** — a mechanism for slowing producers when consumers cannot keep up.
- **Bounded context** — an explicit boundary within which a domain model applies.
- **Canary release** — deploying to a small share of traffic first.
- **Circuit breaker** — a pattern that stops calls to a failing dependency.
- **Error budget** — the amount of unreliability allowed by a service level objective.
- **Idempotent** — an operation that has the same effect whether run once or many times.
- **Outbox pattern** — writing events to a table in the same transaction as state changes.
- **p95** — the 95th percentile, the value below which 95% of observations fall.
- **RPO** — recovery point objective, the maximum tolerable data loss measured in time.
- **RTO** — recovery time objective, the maximum tolerable downtime.
- **SBOM** — software bill of materials, a list of the components in a build.
- **SLO** — service level objective, a target for a reliability metric.
- **STRIDE** — a threat classification model.
- **Trunk-based development** — working in short-lived branches merged frequently into one main branch.

*End of the Acme Engineering Handbook, version 4.2.*
