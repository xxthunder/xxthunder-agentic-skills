# Architecture

## Purpose

The demo service syncs records from an upstream API.

## System context

One upstream API. No other systems.

## Containers

| Container | Path | Role |
|---|---|---|
| Sync job | `src/sync/` | pulls records from the upstream API |
| Importer | `src/importer/` | imports legacy dumps |

## Components

Not yet documented.

## Key flows

Not yet documented.

## Glossary

Not yet documented.

## Decisions

See the [ADR log](adr/README.md).
