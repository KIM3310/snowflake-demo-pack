# Customization Guide

How to adapt the demos for real customer data or custom scenarios.

## Customization levels

| Level | Scope | Effort | When to use |
|-------|-------|--------|-------------|
| 1 | Rename database / schema | 10 min | Sandbox isolation |
| 2 | Adjust data volume | 30 min | Match customer scale (e.g., 10K vs 10M events) |
| 3 | Swap synthetic for customer data | 2-4 hr | Active POC with real data |
| 4 | Add new dimensions to the schema | 4-8 hr | Customer has additional fields |
| 5 | Add a new industry demo | 1-3 days | Expanding the pack itself |

## Level 1: Database/schema rename

Edit `common/setup.sql`:

```sql
CREATE DATABASE IF NOT EXISTS <CUSTOMER>_POC_PILOT;
```

Search-and-replace across the pack:

```bash
# macOS
find demos common scripts -type f \( -name "*.sql" -o -name "*.py" \) \
    -exec sed -i '' 's/SNOWFLAKE_DEMO_PACK/<CUSTOMER>_POC_PILOT/g' {} \;

# Linux
find demos common scripts -type f \( -name "*.sql" -o -name "*.py" \) \
    -exec sed -i 's/SNOWFLAKE_DEMO_PACK/<CUSTOMER>_POC_PILOT/g' {} \;
```

## Level 2: Data volume

Each demo's `02-load-data.py` has a scale parameter near the top:

| Demo | Parameter | Default | Typical range |
|------|-----------|---------|---------------|
| Finance | `TRANSACTIONS_PER_DAY` | 1,000,000 | 50K — 5M |
| Retail | `CUSTOMERS` | 500,000 | 10K — 5M |
| Manufacturing | `SENSORS * SAMPLES_PER_SEC * SECONDS` | ~8.6M/day | 100K — 100M |
| Healthcare | `PATIENTS` | 50,000 | 5K — 500K |
| Media | `USERS * EVENTS_PER_USER_DAY` | 10M | 1M — 100M |

Customer scale greater than 10x default will require warehouse resizing and Dynamic Table refresh budget review. Consult `docs/cost-estimates.md`.

## Level 3: Swap in customer data

Pattern: keep the target schema stable; replace the data-generator layer with a customer-data-loader layer.

Create `demos/<industry>/02a-load-customer-data.py`:

```python
"""Load customer-provided data into the demo schema.

Invoked in place of 02-load-data.py when SNOWFLAKE_DEMO_CUSTOMER=<name> is set.
"""

from common import connection

def main():
    conn = connection.get_connection()
    cur = conn.cursor()
    # COPY INTO from a customer stage
    cur.execute("""
        COPY INTO GOVERNED.PATIENTS
        FROM @CUSTOMER_STAGE/patients/
        FILE_FORMAT = (TYPE=PARQUET)
        ON_ERROR = 'SKIP_FILE'
    """)
    # Repeat for other tables
    conn.close()
```

Then modify `Makefile` to branch on the environment variable:

```makefile
demo-healthcare:
ifdef SNOWFLAKE_DEMO_CUSTOMER
	python demos/04-healthcare-ehr-governed-analytics/02a-load-customer-data.py
else
	python demos/04-healthcare-ehr-governed-analytics/02-load-data.py
endif
	snow sql -f demos/04-healthcare-ehr-governed-analytics/01-setup.sql
	python demos/04-healthcare-ehr-governed-analytics/03-fraud-model.py
```

Validation checklist when swapping data:

- [ ] Column names and types match the demo's expected schema.
- [ ] Nullability of critical columns matches (or the policy logic is updated).
- [ ] Facility or tenant dimension is populated (otherwise row access policies evaluate to FALSE for all rows).
- [ ] At least 100 rows load — tiny data hides policy bugs.
- [ ] The ADR for this customization is written (see `docs/adr/` pattern).

## Level 4: Adding dimensions

If the customer has a field the demo schema lacks — say, "payer_tier" in the healthcare claims table — add it in three places consistently:

1. **`01-setup.sql`** — add the column to the table DDL, tag it appropriately:
   ```sql
   ALTER TABLE GOVERNED.CLAIMS ADD COLUMN PAYER_TIER STRING;
   ALTER TABLE GOVERNED.CLAIMS MODIFY COLUMN PAYER_TIER
       SET TAG POLICY.SENSITIVITY = 'Financial';
   ```
2. **`02-load-data.py`** — populate the new column in the data generator, or document that it's populated from customer data.
3. **`04-analytics.sql`** — add at least one query that uses the new column so the SE can demonstrate it.

Do not add a column without also adding a query that uses it. Unreferenced columns drift into tech debt.

## Level 5: New industry demo

To add a 6th industry:

1. **Copy** the folder closest in architecture pattern (e.g., `03-manufacturing-*` if IoT-streaming-like, `04-healthcare-*` if governance-heavy).
2. **Rename** everything consistently.
3. **Write the `README.md` first** using the per-demo template. Force yourself to articulate the business problem before writing code.
4. **Write the `value-case.md`** next. If you can't write a credible value case, the demo isn't worth building.
5. **Write the `architecture.md`** with a mermaid diagram.
6. **Build the SQL + Python** following the existing patterns.
7. **Write the `presentations/<industry>-5min-pitch.md`**.
8. **Add to the root README** `The 5 Demos` table, expand to 6.
9. **Add to `Makefile`** the `demo-<industry>` target.
10. **Add to `scripts/run_all.sh`** and `scripts/teardown.sh`.
11. **Write an ADR** documenting what Snowflake features you chose and why.

## Common customization anti-patterns

| Anti-pattern | Why it's bad | What to do instead |
|--------------|--------------|-------------------|
| Copying a demo, editing in place, losing the original | You lose the reset path when POC pivots | Fork the full pack for the customer, maintain upstream separately |
| Adding a query to `04-analytics.sql` without a value-case link | Unmoored technical feature tour | Every query should support a value-case bullet |
| Customer-specific secrets committed to the fork | Security incident waiting to happen | Use `.env` + Snowflake secrets; never commit |
| Using a demo role (CARE_NURSE_FACILITY_A, etc.) as a customer role | Role names leak demo context into POC artifacts | Rename to customer's IAM group names (e.g., `CLIN_ANALYTICS_USER`) |
| Data volume scaled by 100x without warehouse resize | Dynamic Table refresh times blow up, demo fails mid-call | Always test with production-scale data before the customer call |

## Style conventions for customizations

- Keep the 7-file-per-demo convention. Don't add ad-hoc files.
- Snake-case for SQL identifiers, kebab-case for filenames, PascalCase for Python classes.
- Every customization that changes policy logic gets an ADR in `docs/adr/`.
- Every mermaid diagram stays in `architecture.md`. Don't add diagrams to READMEs directly.
