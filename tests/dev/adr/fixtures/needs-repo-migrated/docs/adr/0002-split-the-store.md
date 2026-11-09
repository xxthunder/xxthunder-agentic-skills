# ADR-0002: Split the store

```{decision} Split the store
:id: ADR-0002
:status: Accepted
```

**Status**: Accepted
**Date**: 2026-11-09
**Supersedes**: [ADR-0001](0001-keep-the-log.md)

## Context

One store is too big.

## Decision

We split the store in two.

## Alternatives considered

Keep one store: it keeps growing.

## Consequences

Two stores need two backups.
