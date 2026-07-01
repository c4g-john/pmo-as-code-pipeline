---
kind: risk-register
id: onboarding-risk-register
title: Customer Onboarding — Risk Register
owner: alex.kim
status: approved
---

## Overview

Risks tracked for the customer onboarding programme. Each risk links to the
requirement or product requirement it threatens.

## Risks

- **RISK-001** (threatens: BR-001): Data migration from the legacy setup tool may slip the MVP and delay the onboarding-time reduction. Probability: High. Impact: High. Owner: alex.kim. Response: Dual-run the old and new flows for two weeks with a manual CSV fallback.
- **RISK-002** (threatens: PR-015): Progress-email deliverability may fall below target in some regions, weakening the notification requirement. Probability: Medium. Impact: Medium. Owner: priya.n. Response: Add a fallback SMS notification and monitor delivery rates per region.
