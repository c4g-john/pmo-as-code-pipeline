---
kind: adr
id: onboarding-adr-log
title: Customer Onboarding — Architecture Decisions
owner: alex.kim
status: approved
---

## Overview

Architecture decisions for the self-serve onboarding flow. Each decision links
to the requirement it affects.

## Decisions

- **ADR-001** (affects: FR-101): Server-side validation for onboarding. Status: accepted. Context: client-only checks can be bypassed, risking invalid accounts. Decision: validate all required fields server-side before account creation. Consequences: marginally higher latency; materially stronger data integrity.
- **ADR-002** (affects: NFR-05): Queued delivery for progress emails. Status: accepted. Context: sending inline risks blocking the request path and breaching the 5-minute target. Decision: enqueue progress emails and send asynchronously. Consequences: sub-5-minute delivery is achievable; adds a queue dependency to operate.
