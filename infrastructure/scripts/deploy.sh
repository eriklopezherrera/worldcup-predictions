#!/usr/bin/env bash
# Deploy the full stack: infra first, then the frontend rebuilt with the
# resulting API URL + Cognito IDs baked in.
#
# Usage: ./scripts/deploy.sh [env]      (env defaults to prod)
# Requires: aws cli (profile via AWS_PROFILE, default "worldcup"), cdk, docker, node.
set -euo pipefail

ENV="${1:-prod}"
export AWS_PROFILE="${AWS_PROFILE:-worldcup}"

INFRA_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND_DIR="$INFRA_DIR/../frontend"
OUTPUTS="$INFRA_DIR/outputs-$ENV.json"

cd "$FRONTEND_DIR"
[ -d node_modules ] || npm ci
# First pass: any build so the FrontendStack asset exists at synth time.
[ -d dist ] || npm run build

cd "$INFRA_DIR"
cdk deploy --all --context env="$ENV" --require-approval never --outputs-file "$OUTPUTS"

# Second pass: bake real outputs into the frontend build and redeploy it.
node -e "
const o = require('$OUTPUTS');
const env = '$ENV';
const fs = require('fs');
const lines = [
  'VITE_API_BASE_URL=' + o['worldcup-' + env + '-api'].ApiUrl,
  'VITE_COGNITO_USER_POOL_ID=' + o['worldcup-' + env + '-auth'].UserPoolId,
  'VITE_COGNITO_CLIENT_ID=' + o['worldcup-' + env + '-auth'].ClientId,
  'VITE_ENVIRONMENT=' + env,
];
fs.writeFileSync('$FRONTEND_DIR/.env.production', lines.join('\n') + '\n');
console.log(lines.join('\n'));
"

cd "$FRONTEND_DIR"
npm run build

cd "$INFRA_DIR"
cdk deploy "worldcup-$ENV-frontend" --context env="$ENV" --require-approval never

echo "Done. Frontend: $(node -e "console.log(require('$OUTPUTS')['worldcup-$ENV-frontend'].FrontendUrl)")"
