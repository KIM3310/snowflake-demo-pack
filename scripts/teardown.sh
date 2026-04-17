#!/usr/bin/env bash
# Teardown all Snowflake objects created by the demo pack.
# WARNING: This drops the database and all demo roles/users.

set -euo pipefail

DRY_RUN="${SNOWFLAKE_DEMO_DRY_RUN:-1}"
DB_NAME="${SNOWFLAKE_DEMO_DB:-SNOWFLAKE_DEMO_PACK}"

cat <<EOF
===============================================
  Snowflake Demo Pack — Teardown
===============================================
  Database:  $DB_NAME
  Dry run:   $DRY_RUN

This will drop:
  - Database $DB_NAME (all schemas, tables, views, policies, tags)
  - Warehouse DEMO_WH
  - Roles: CARE_NURSE_FACILITY_A, CARE_NURSE_FACILITY_B,
           RESEARCHER_NATIONAL, FINANCE_ANALYST, QUALITY_IMPROVEMENT
  - Users: demo_nurse_a, demo_nurse_b, demo_researcher,
           demo_finance, demo_qi

EOF

if [[ "$DRY_RUN" != "1" ]]; then
    read -rp "Type the database name ($DB_NAME) to confirm: " confirm
    if [[ "$confirm" != "$DB_NAME" ]]; then
        echo "Aborted."
        exit 1
    fi
fi

TEARDOWN_SQL=$(cat <<SQL
USE ROLE ACCOUNTADMIN;

DROP USER IF EXISTS demo_nurse_a;
DROP USER IF EXISTS demo_nurse_b;
DROP USER IF EXISTS demo_researcher;
DROP USER IF EXISTS demo_finance;
DROP USER IF EXISTS demo_qi;

DROP ROLE IF EXISTS CARE_NURSE_FACILITY_A;
DROP ROLE IF EXISTS CARE_NURSE_FACILITY_B;
DROP ROLE IF EXISTS RESEARCHER_NATIONAL;
DROP ROLE IF EXISTS FINANCE_ANALYST;
DROP ROLE IF EXISTS QUALITY_IMPROVEMENT;

DROP DATABASE IF EXISTS $DB_NAME;
DROP WAREHOUSE IF EXISTS DEMO_WH;
SQL
)

if [[ "$DRY_RUN" == "1" ]]; then
    echo "(dry-run) would execute:"
    echo "$TEARDOWN_SQL"
else
    echo "$TEARDOWN_SQL" | snow sql --filename /dev/stdin
    echo ""
    echo "Teardown complete. All demo objects removed."
fi
