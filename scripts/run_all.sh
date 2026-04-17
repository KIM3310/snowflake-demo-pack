#!/usr/bin/env bash
# Run all 5 demos end-to-end in sequence.
# Safe to run repeatedly — each demo's setup is idempotent.

set -euo pipefail

PACK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PACK_ROOT"

DRY_RUN="${SNOWFLAKE_DEMO_DRY_RUN:-1}"

echo "==============================================="
echo "  Snowflake Demo Pack — Run All"
echo "==============================================="
echo "PACK_ROOT: $PACK_ROOT"
echo "DRY_RUN:   $DRY_RUN"
echo ""

run_demo() {
    local demo_name="$1"
    local demo_dir="demos/$demo_name"

    echo "-----------------------------------------------"
    echo "  $demo_name"
    echo "-----------------------------------------------"

    if [[ ! -d "$demo_dir" ]]; then
        echo "SKIP: $demo_dir does not exist"
        return 0
    fi

    if [[ "$DRY_RUN" == "1" ]]; then
        echo "(dry-run) would execute:"
        echo "   snow sql -f $demo_dir/01-setup.sql"
        echo "   python $demo_dir/02-load-data.py"
        echo "   python $demo_dir/03-fraud-model.py"
        echo "   snow sql -f $demo_dir/04-analytics.sql"
    else
        echo "1. Setup"
        snow sql -f "$demo_dir/01-setup.sql"

        echo "2. Load data"
        python "$demo_dir/02-load-data.py"

        echo "3. Apply model / policy"
        python "$demo_dir/03-fraud-model.py"

        echo "4. Analytics"
        snow sql -f "$demo_dir/04-analytics.sql"
    fi

    echo ""
}

# Common setup first
if [[ "$DRY_RUN" == "1" ]]; then
    echo "(dry-run) would execute common setup: common/setup.sql"
else
    snow sql -f common/setup.sql
fi
echo ""

run_demo "01-finance-fraud-detection"
run_demo "02-retail-customer-360"
run_demo "03-manufacturing-predictive-maintenance"
run_demo "04-healthcare-ehr-governed-analytics"
run_demo "05-media-content-recommendation"

echo "==============================================="
echo "  All demos completed"
echo "==============================================="

if [[ "$DRY_RUN" == "1" ]]; then
    echo ""
    echo "This was a dry run. To run against a real Snowflake account:"
    echo "  export SNOWFLAKE_DEMO_DRY_RUN=0"
    echo "  export SNOWFLAKE_ACCOUNT=your-account"
    echo "  export SNOWFLAKE_USER=your-user"
    echo "  export SNOWFLAKE_PASSWORD=your-password"
    echo "  $0"
fi

echo ""
echo "Remember to teardown when done:"
echo "  ./scripts/teardown.sh"
