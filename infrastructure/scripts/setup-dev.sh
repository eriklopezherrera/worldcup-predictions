#!/usr/bin/env bash
# One-time stand-up of a fresh dev environment: deploy all stacks, run
# migrations, and seed the WC2026 data. Takes ~15-20 min the first time
# (RDS provisioning dominates). After this, use deploy-dev-code.sh for fast
# per-test redeploys — the heavy stacks stay up and are skipped when unchanged.
#
# Usage: ./scripts/setup-dev.sh [env]      (env defaults to dev; refuses prod)
set -euo pipefail

ENV="${1:-dev}"
if [ "$ENV" = "prod" ]; then
  echo "setup-dev.sh is for disposable envs only; use deploy.sh for prod." >&2
  exit 1
fi

SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"

"$SCRIPTS_DIR/deploy.sh" "$ENV"
"$SCRIPTS_DIR/migrate.sh" "$ENV"
"$SCRIPTS_DIR/migrate.sh" "$ENV" seed

echo "Dev environment '$ENV' is up and seeded."
echo "Grant yourself admin: ./scripts/migrate.sh $ENV make_admin you@example.com"
