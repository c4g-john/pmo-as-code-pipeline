---
kind: prd
id: onboarding-prd
title: Customer Onboarding — Product Requirements
owner: alex.kim
status: approved
---

## Overview

The onboarding product replaces manual, ticket-driven setup with a self-serve
flow and proactive progress communication.

## Product Requirements

- **PR-014** (traces: BR-001): The product shall provide a self-serve onboarding flow that requires no manual setup step.
- **PR-015** (traces: BR-002): The product shall email each customer a progress summary at every onboarding stage.

## Acceptance Criteria

- **AC-001** (verifies: PR-014): Given a new customer with valid details, when they complete the self-serve wizard, then an active account exists and no support ticket is created.
- **AC-002** (verifies: PR-015): Given a customer part-way through onboarding, when a stage completes, then a progress email is sent within 5 minutes.
