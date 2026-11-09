# Changelog

## 1.11.0 — 2026-11-09

- `requirements` on `Task` and `TaskQuoteResponse` (`TaskRequirements`): each vehicle Relay looks for and the equipment a rider on it needs, for example a box on a motorcycle for food. See [the box a task needs](https://docs.sendrelay.com.ng/concepts/dispatch#the-box-a-task-needs).
- `client.presence.get()` takes a job: `taskType`, `vehicleType` (a list, sent comma-separated), `hasBox`, `hasRefrigeration`, `hasAirConditioning`, `estimatedWeight` and `estimatedSize`, with the quote's meanings. It then counts only riders who could take that job and returns `requirements`. Without `taskType` the map is unchanged.

## 1.10.0 — 2026-11-08

- `relay.events.list()` and `relay.events.list_all()`: the event log, every event for your account and mode, kept for 30 days. `types` filters by event type.
- `relay.tasks.events(task_id)`: every event about one task, oldest first.
- `relay.claims`: insurance claims on a task, for insured goods lost, stolen or damaged after collection. `get`, `create_upload` (a URL to PUT one photo or PDF to), `file`, `respond` and `withdraw`, on `Relay` and `AsyncRelay`. Live keys only.
- `relay.webhooks.redeliver(webhook_id, {"eventId": ...})`: send a logged event to an endpoint again, with the same id.
- `updatedSince` on `tasks.list()` and `list_all()`: tasks changed since a time, in `updatedAt` order, for reconciliation jobs.
- `revision` and `currency` on tasks. Task events carry `data["revision"]`: apply an event only if it is higher than the revision you stored.
- `tasks.update(task_id, body)` edits notes, externalId, and a stop's instructions and contact; `tasks.tracking_link(task_id, body=None)` returns a hosted tracking page. Tasks return `requirePhoto`.

## 1.9.0 — 2026-11-06

- Insurance on tasks: `"insured": False` on create and quote turns it off for that task. It is on by default.
- `insuranceFee` and `insuredValue` on quote and create pricing. The premium is now its own line: VAT applies to it, and fare premiums and the platform fee no longer do.

## 1.8.0 — 2026-11-03

- Keep looking for a rider and scheduled pickups ([dispatch strategies](https://docs.sendrelay.com.ng/tasks/keep-looking-and-scheduling)).
- `dispatch` on create and quote (`DispatchRequest`), `task["dispatch"]` (`TaskDispatch`) with the search window, and the `SCHEDULED` and `SEARCHING` statuses are typed.
- `relay.tasks.simulate_advance(task_id)` (sync and asyncio, test keys) starts a booking's search now.
- Task requests accept an optional `reference` on items, and optional `countryCode` (ISO 3166-1 alpha-2) and `postalCode` on stage locations. They are returned on the task when sent, and not used in pricing yet.
- Statuses and webhook event types this version doesn't list arrive as their raw strings; `TaskStatus` is now typed as known values or `str`. Relay will add task statuses (for example for tasks that keep searching for a rider), so treat a status you don't recognise as still in progress.

## 1.7.0 — 2026-10-29

- First release, versioned with the other Relay server SDKs (they move together). Matches the shared SDK conformance suite (packages/sdks/conformance).
