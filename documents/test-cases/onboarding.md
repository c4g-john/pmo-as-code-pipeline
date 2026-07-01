---
kind: test-cases
id: onboarding-test-cases
title: Customer Onboarding — Test Cases
owner: priya.n
status: approved
---

## Overview

Test cases covering the acceptance criteria for the self-serve onboarding flow.

## Test Cases

- **TC-001** (tests: AC-001): Steps: complete the self-serve wizard with valid customer details. Expected: the account is active and zero support tickets were created.
- **TC-002** (tests: AC-002): Steps: complete an onboarding stage for an in-progress customer. Expected: a progress email is received within 5 minutes.
