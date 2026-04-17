# Healthcare — Governed EHR Analytics: 5-Minute SE Pitch

*Delivery script for a pre-sales conversation. Total runtime: 5 minutes.*

---

## 0:00 — 0:30 — Anchor the problem

> "Your analytics team supports 15-plus stakeholder groups. Each group needs a slightly different slice of the same patient data. Today, your EDW maintains 6 to 12 extract copies to handle this — each with its own ETL pipeline, its own refresh schedule, its own access list, its own compliance audit surface. Every copy is a breach risk. Your compliance team spends 6 weeks a year just gathering evidence for audits. Your researchers wait 26 days for a de-identified cohort."

**What to watch**: the CISO or compliance leader is your anchor in the healthcare conversation. If they're not in the room, confirm before continuing.

## 0:30 — 1:15 — Show the architecture

Open `demos/04-healthcare-ehr-governed-analytics/architecture.md`.

> "Everything you see runs on one base table set. Row Access Policies enforce the 'which rows' dimension. Tag-Based Masking Policies enforce the 'which columns, shaped how' dimension. Secure Views are the only consumption surface — stakeholder groups never touch the base tables. Access History records every row and column accessed by every role, 365-day retention."

**What to emphasize**: "Policy, not copy." This is the phrase that lands.

## 1:15 — 2:30 — Live query walk-through — *this is the demo's decisive moment*

> "Watch what happens when I run the exact same SQL as three different roles."

Execute, role-switching between each:

1. As `CARE_NURSE_FACILITY_A`: `SELECT COUNT(*) FROM PATIENTS;` → returns ~3,200.
2. As `RESEARCHER_NATIONAL`: same SQL → returns 50,000 (de-identified).
3. As `FINANCE_ANALYST`: same SQL → returns 0 (no grant).

> "Same SQL. Three different answers. Enforced by the platform, not by me writing three different queries. The policy is the contract."

Follow with:

4. As `CARE_NURSE_FACILITY_A`: `SELECT MRN, FIRST_NAME, DATE_OF_BIRTH FROM PATIENTS LIMIT 5;` → sees actual PHI.
5. As `RESEARCHER_NATIONAL`: same SQL → sees hashed IDs, year-only DOB.

> "Same SQL. Masked automatically based on who's asking."

## 2:30 — 3:15 — The audit answer

Run the Access History lookup: "Who accessed patient MRN-00042 in the last 90 days?"

> "Your compliance team needs 6 weeks today. This query takes 10 seconds. Your auditor is a SELECT statement away from the answer."

**What to emphasize**: this is the CISO's "show me that again" moment.

## 3:15 — 4:15 — The TCO framing

| Current state (typical) | This pattern |
|-------------------------|--------------|
| 6-12 extract copies, 6-12 pipelines, 6-12 ACLs | 1 governed layer |
| $420K/yr extract fleet maintenance | Consolidation savings; Snowflake consumption typically 50-60% of prior cost |
| 26-day cohort request lead time | 3-day (IRB review becomes the gating item) |
| 6-week compliance audit cycle | 2-day evidence gathering |
| 2 historical over-share incidents per 5 years | Zero over-share since cutover (in reference customers) |

> "This isn't a software modernization. It's a compliance operating-model change."

## 4:15 — 4:45 — Proof-of-concept offer

> "6-week POC with a carve-out scope. You choose one service line — say, cardiology. You bring 3 months of de-identified encounter data. I bring the governed schema, the policy matrix, and role mappings tied to your Active Directory groups. At the end, your research, QI, finance, and care-management stakeholders all consume from the same substrate. Your compliance team runs the audit query live in the outcome review."

## 4:45 — 5:00 — Close with the ask

> "Who owns your current extract-request process? That's where the pain centralizes. Can you make an intro to the analytics leader and the HIPAA privacy officer together?"

---

## Objection bank

| Objection | Response |
|-----------|----------|
| "We can't put PHI in the cloud." | "Snowflake is HIPAA-eligible with signed BAA. Data is encrypted at rest with customer-managed keys if you need them. Region pinning is available. Data never leaves your account boundary. Your CISO should evaluate the actual control environment, not the hosting model." |
| "Our EHR vendor won't let us extract." | "You're already extracting for billing and QI. The question isn't whether to extract — it's whether to maintain 9 extracts or 1." |
| "Row access policies sound like they can be bypassed by SYSADMIN." | "Correct — and Access History captures SYSADMIN access, flagged distinctly. Your compliance program audits SYSADMIN sessions separately. Same as any privileged-access program." |
| "What about break-glass scenarios?" | "Implement a BREAK_GLASS role with an Access History alert on every use. Standard healthcare pattern." |
| "Research IRB still takes weeks regardless." | "Correct. The lead-time reduction is from the engineering build-out (weeks) to the view definition (hours). IRB is the gating item post-cutover." |

## What to bring

- Pre-loaded account running `make demo-healthcare`.
- **Critical**: have the 5 demo roles pre-logged-in in 5 browser tabs. The role-switch demo is the pitch.
- `value-case.md` as leave-behind.
- Access to both the analytics leader and privacy officer simultaneously. This is the one demo where the legal/compliance conversation is primary.
