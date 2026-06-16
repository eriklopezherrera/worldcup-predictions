#!/usr/bin/env bash
# Deploy the full stack: infra first, then the frontend rebuilt with the
# resulting API URL + Cognito IDs baked in.
#
# Usage: ./scripts/deploy.sh [env]      (env defaults to prod)
# Requires: aws cli (profile via AWS_PROFILE, default "worldcup"), cdk, docker, node.
set -euo pipefail

ENV="${1:-prod}"
export AWS_PROFILE="${AWS_PROFILE:-worldcup}"
# The whole stack lives in us-east-1; pin it so a bare cdk/aws call does not
# fall back to the caller's default region (e.g. us-east-2).
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-$AWS_REGION}"

INFRA_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND_DIR="$INFRA_DIR/../frontend"
OUTPUTS="$INFRA_DIR/outputs-$ENV.json"

# cdk.json runs `python app.py`, so the CDK venv must be on PATH. Activate it
# if present (Windows uses Scripts/, Unix uses bin/).
if [ -f "$INFRA_DIR/.venv/Scripts/activate" ]; then
  # shellcheck disable=SC1091
  source "$INFRA_DIR/.venv/Scripts/activate"
elif [ -f "$INFRA_DIR/.venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$INFRA_DIR/.venv/bin/activate"
fi

cd "$FRONTEND_DIR"
[ -d node_modules ] || npm ci
# First pass: build so the FrontendStack asset exists at synth time. Always
# rebuild — a leftover dist/ may be baked for a different env (e.g. a prod
# bundle), and reusing it would deploy the wrong API URL + Cognito IDs. The
# second pass below rebuilds again with the real outputs anyway.
npm run build

cd "$INFRA_DIR"
cdk deploy --all --context env="$ENV" --require-approval never --outputs-file "$OUTPUTS"

# Second pass: bake real outputs into the frontend build and redeploy it.
# Run node from INFRA_DIR and reference files by basename so we never pass a
# Git-Bash mount path (/c/Users/...) that Windows node cannot resolve. Paths
# are passed via env vars rather than interpolated into the JS string.
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

cd "$FRONTEND_DIR"
npm run build

cd "$INFRA_DIR"
cdk deploy "worldcup-$ENV-frontend" --context env="$ENV" --require-approval never

echo "Done. Frontend: $(node -e "console.log(require('$OUTPUTS')['worldcup-$ENV-frontend'].FrontendUrl)")"
