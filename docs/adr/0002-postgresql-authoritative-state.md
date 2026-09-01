# ADR 0002: PostgreSQL-Backed State Is Authoritative

## Context
The game is persistent and multiplayer.

## Decision
Canonical shared game state is stored in PostgreSQL-backed domain models. Redis may hold ephemeral/distributed coordination state.

## Consequences
State survives reconnects and restarts, and concurrency can use database transactions/locking.
