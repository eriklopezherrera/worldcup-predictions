#!/usr/bin/env bash
# Fully decommission a disposable environment (dev/staging) to stop its
# ~$32/mo running cost. This is NOT a per-test step — networking + data + auth
# are torn down, so RDS data and Cognito accounts are lost and the next
# stand-up takes ~15-20 min again. Use deploy-dev-code.sh between tests instead.
#
# Also force-purges the RDS-managed secret: on `cdk destroy` Secrets Manager
# keeps `worldcup/<env>/db-admin` for a 7-day recovery window, and a rebuild
# within that window fails with "secret already scheduled for deletion".
#
# Usage: ./scripts/destroy.sh <env>      (refuses prod)
set -euo pipefail

ENV="${1:-}"
if [ -z "$ENV" ]; then
  echo "Usage: ./scripts/destroy.sh <env>   (dev|staging)" >&2
  exit 1
fi
if [ "$ENV" = "prod" ]; then
  echo "Refusing to destroy prod." >&2
  exit 1
fi

export AWS_PROFILE="${AWS_PROFILE:-worldcup}"
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-$AWS_REGION}"

INFRA_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUTS="$INFRA_DIR/outputs-$ENV.json"

# Activate the CDK venv (cdk.json runs `python app.py`).
if [ -f "$INFRA_DIR/.venv/Scripts/activate" ]; then
  # shellcheck disable=SC1091
  source "$INFRA_DIR/.venv/Scripts/activate"
elif [ -f "$INFRA_DIR/.venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$INFRA_DIR/.venv/bin/activate"
fi

read -r -p "This will DELETE all '$ENV' stacks and data. Type '$ENV' to confirm: " CONFIRM
[ "$CONFIRM" = "$ENV" ] || { echo "Aborted."; exit 1; }

cd "$INFRA_DIR"
cdk destroy --all --context env="$ENV" --force

# Force-delete the RDS secret so a rebuild does not hit the recovery-window
# collision. Ignore failure if it is already gone.
aws secretsmanager delete-secret \
  --secret-id "worldcup/$ENV/db-admin" \
  --force-delete-without-recovery >/dev/null 2>&1 \
  && echo "Purged secret worldcup/$ENV/db-admin." \
  || echo "Secret worldcup/$ENV/db-admin not found (already gone)."

rm -f "$OUTPUTS"
echo "Environment '$ENV' decommissioned."
