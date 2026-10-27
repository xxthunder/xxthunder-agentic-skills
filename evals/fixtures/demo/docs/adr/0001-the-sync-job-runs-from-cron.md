# ADR-0001 — The sync job runs from cron

**Status**: Accepted
**Date**: 2026-09-01

## Context

The upstream API allows one full sync per hour. The service has no scheduler of its own.

## Decision

The sync job is a command that cron starts once an hour.

## Alternatives considered

- A long-running worker with its own timer. It lost because a crash stopped every later sync
  until someone noticed.

## Consequences

A run that takes longer than an hour overlaps the next one. The job takes a lock file to
skip such a run.
