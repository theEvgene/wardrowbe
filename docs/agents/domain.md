# Domain documentation

Wardrowbe currently uses a single bounded context.

## Layout

- `CONTEXT.md` — domain overview, vocabulary, actors, invariants, capabilities, and important workflows.
- `docs/adr/` — architecture decision records for decisions that constrain future implementation.

These documents may be created lazily when domain modeling or an architectural decision requires them.

## How agents use domain documentation

Before exploring or changing domain behavior:

1. Read the root `CONTEXT.md` when it exists.
2. Read relevant records in `docs/adr/`.
3. Use the vocabulary defined in `CONTEXT.md` consistently in code, issues, tests, and user-facing text.
4. Check whether the proposed change conflicts with a documented invariant or architecture decision.
5. If documents are absent, continue without blocking the task.

## Updating domain knowledge

Update `CONTEXT.md` when work introduces or materially changes:

- domain terminology;
- actors or permissions;
- business rules and invariants;
- major user workflows;
- boundaries with external systems.

Create an ADR when choosing between meaningful architectural alternatives whose consequences will affect later development.

Do not create an ADR for routine implementation details or easily reversible local choices.

If implementation conflicts with an existing ADR, surface the conflict explicitly instead of silently overriding the decision.
