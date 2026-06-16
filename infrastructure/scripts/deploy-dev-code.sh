#!/usr/bin/env bash
# Fast per-test redeploy of an existing dev environment. Only touches the
# stateless stacks (api / frontend); networking, data (RDS+Redis) and auth are
# left running, so there is no 15-min RDS wait and dev data persists.
#
# Usage:
#   ./scripts/deploy-dev-code.sh [env]            # backend only (default) — ~2 min
#   ./scripts/deploy-dev-code.sh [env] --frontend # frontend only (two-pass build)
#   ./scripts/deploy-dev-code.sh [env] --all      # backend + frontend
#
# env defaults to dev and prod is refused (use deploy.sh for prod).
set -euo pipefail

ENV="${1:-dev}"
TARGET="${2:---api}"
if [ "$ENV" = "prod" ]; then
  echo "deploy-dev-code.sh is for disposable envs only; use deploy.sh for prod." >&2
  exit 1
fi

export AWS_PROFILE="${AWS_PROFILE:-worldcup}"
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-$AWS_REGION}"

INFRA_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND_DIR="$INFRA_DIR/../frontend"
OUTPUTS="$INFRA_DIR/outputs-$ENV.json"

# cdk.json runs `python app.py`, so the CDK venv must be on PATH.
if [ -f "$INFRA_DIR/.venv/Scripts/activate" ]; then
  # shellcheck disable=SC1091
  source "$INFRA_DIR/.venv/Scripts/activate"
elif [ -f "$INFRA_DIR/.venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$INFRA_DIR/.venv/bin/activate"
fi

deploy_api() {
  cd "$INFRA_DIR"
  cdk deploy "worldcup-$ENV-api" --context env="$ENV" --require-approval never \
    --outputs-file "$OUTPUTS"
}

deploy_frontend() {
  [ -f "$OUTPUTS" ] || { echo "Missing $OUTPUTS — run setup-dev.sh $ENV first." >&2; exit 1; }
  # Bake the existing stack outputs into the Vite build, then redeploy frontend.
  ( cd "$INFRA_DIR" && OUTPUTS_FILE="outputs-$ENV.json" ENV_NAME="$ENV" node -e '
  const path = require("path");
  const fs = require("fs");
  const o = require(path.resolve(process.cwd(), process.env.OUTPUTS_FILE));
  const env = process.env.ENV_NAME;
  const lines = [
    "VITE_API_BASE_URL=" + o["worldcup-" + env + "-api"].ApiUrl,
    "VITE_COGNITO_USER_POOL_ID=" + o["worldcup-" + env + "-auth"].UserPoolId,
    "VITE_COGNITO_CLIENT_ID=" + o["worldcup-" + env + "-auth"].ClientId,
    "VITE_ENVIRONMENT=" + env,
  ];
  const out = path.resolve(process.cwd(), "..", "frontend", ".env.production");
  fs.writeFileSync(out, lines.join("\n") + "\n");
  console.log(lines.join("\n"));
  ' )
  cd "$FRONTEND_DIR" && npm run build
  cd "$INFRA_DIR"
  cdk deploy "worldcup-$ENV-frontend" --context env="$ENV" --require-approval never
}

case "$TARGET" in
  --api)      deploy_api ;;
  --frontend) deploy_frontend ;;
  --all)      deploy_api && deploy_frontend ;;
  *) echo "Unknown target '$TARGET' (expected --api | --frontend | --all)" >&2; exit 1 ;;
esac

echo "Redeployed '$TARGET' for env '$ENV'."
