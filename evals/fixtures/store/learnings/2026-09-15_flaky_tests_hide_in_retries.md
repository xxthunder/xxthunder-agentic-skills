# Flaky tests hide in retries

**Origin**: demo `DEMO-002`, 2026-09-15

## Claim

A CI retry turns a flaky test into a slow green build, and the flake is never fixed.

## Why it holds
*(drafted by the agent)*

Nobody reads the log of a green build.

## Consequence
*(drafted by the agent)*

Report a retried pass as a failure.
