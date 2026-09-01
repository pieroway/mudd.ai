# ADR 0001: Start as a Modular Monolith

## Context
The project has many future systems but limited early operational complexity.

## Decision
Use a modular monolith initially.

## Alternatives considered
Microservices from the start.

## Consequences
Simpler local development, testing, and transactions. Split services later only when justified.
