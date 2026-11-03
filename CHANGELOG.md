# Changelog

## 1.8.0 — 2026-11-03

- Keep looking for a rider and scheduled pickups ([dispatch strategies](https://docs.sendrelay.com.ng/tasks/keep-looking-and-scheduling)).
- `dispatch` on create and quote (`DispatchRequest`), `task["dispatch"]` (`TaskDispatch`) with the search window, and the `SCHEDULED` and `SEARCHING` statuses are typed.
- `relay.tasks.simulate_advance(task_id)` (sync and asyncio, test keys) starts a booking's search now.
- Task requests accept an optional `reference` on items, and optional `countryCode` (ISO 3166-1 alpha-2) and `postalCode` on stage locations. They are returned on the task when sent, and not used in pricing yet.
- Statuses and webhook event types this version doesn't list arrive as their raw strings; `TaskStatus` is now typed as known values or `str`. Relay will add task statuses (for example for tasks that keep searching for a rider), so treat a status you don't recognise as still in progress.

## 1.7.0 — 2026-10-29

- First release, versioned with the other Relay server SDKs (they move together). Matches the shared SDK conformance suite (packages/sdks/conformance).
