#!/usr/bin/env bash
# Run DB operations against a deployed environment via the ops Lambda
# (the RDS instance lives in a private subnet — there is no direct access).
#
# Usage:
#   ./scripts/migrate.sh [env]                      # alembic upgrade head
#   ./scripts/migrate.sh [env] seed                 # load WC2026 teams + matches
#   ./scripts/migrate.sh [env] make_admin you@x.com # grant admin rights
set -euo pipefail

ENV="${1:-prod}"
ACTION="${2:-migrate}"
IDENTIFIER="${3:-}"
export AWS_PROFILE="${AWS_PROFILE:-worldcup}"

PAYLOAD="{\"action\": \"$ACTION\"}"
if [ "$ACTION" = "make_admin" ]; then
  [ -n "$IDENTIFIER" ] || { echo "make_admin requires an email/username argument"; exit 1; }
  PAYLOAD="{\"action\": \"make_admin\", \"identifier\": \"$IDENTIFIER\"}"
fi

OUT="$(mktemp)"
aws lambda invoke \
  --function-name "worldcup-$ENV-ops" \
  --payload "$PAYLOAD" \
  --cli-binary-format raw-in-base64-out \
  "$OUT" >&2

cat "$OUT"
echo
