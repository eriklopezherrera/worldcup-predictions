# AWS Infrastructure — CDK Specification

## Overview
Infrastructure as Code using AWS CDK v2 (Python).
Location: `infrastructure/`
Entry point: `infrastructure/app.py`

All stacks accept `env_name` parameter: `dev`, `staging`, or `prod`.

---

## Stack Dependency Order
```
NetworkingStack
    └── DataStack (needs VPC)
AuthStack (independent)
FrontendStack (independent — S3 + CloudFront only)
    └── ApiStack (needs VPC, DB, Redis, Cognito, CloudFront domain for CORS)
```

Stack names are `worldcup-{env}-{networking|data|auth|frontend|api}`.

> **Note:** the original `SyncStack` (EventBridge + api-football sync worker) was
> dropped. Tournament data is loaded from `backend/worldcup2026_teams.json` and
> `backend/worldcup2026_matches.json`, and match results are entered manually via
> the admin endpoints. Migrations and data loads run through an **ops Lambda**
> (`worldcup-{env}-ops`, handler `app.workers.ops.handler`) invoked by
> `scripts/migrate.sh`.

The frontend build bakes in `VITE_API_BASE_URL` + Cognito IDs, so
`scripts/deploy.sh` is two-pass: deploy all stacks, write
`frontend/.env.production` from the stack outputs, rebuild, redeploy the
frontend stack.

---

## `NetworkingStack`
File: `infrastructure/stacks/networking_stack.py`

Creates:
- VPC with 2 AZs, 2 public subnets, 2 private subnets (with NAT Gateway)
- Security Groups:
  - `lambda_sg`: outbound 443 (HTTPS for Cognito/APIs), outbound 5432 (RDS), outbound 6379 (Redis)
  - `rds_sg`: inbound 5432 from `lambda_sg` only
  - `redis_sg`: inbound 6379 from `lambda_sg` only
- Exports: `vpc`, `lambda_sg`, `rds_sg`, `redis_sg`, private subnet IDs

All environments use 2 AZs (an RDS subnet group requires two) with a single
NAT gateway. The Lambda SG also allows outbound 443 (Cognito JWKS, Secrets
Manager, cognito-idp); DNS to the Amazon-provided resolver bypasses SGs.

---

## `DataStack`
File: `infrastructure/stacks/data_stack.py`

### RDS PostgreSQL
```python
rds.DatabaseInstance(
    instance_identifier=f"worldcup-{env_name}",
    engine=rds.DatabaseInstanceEngine.postgres(
        version=rds.PostgresEngineVersion.of("15", "15")
    ),
    instance_type=ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MICRO),
    vpc=networking.vpc,
    vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
    security_groups=[networking.rds_sg],
    database_name="worldcuppredictions",
    credentials=rds.Credentials.from_generated_secret(
        "wcadmin", secret_name=f"worldcup/{env_name}/db-admin"
    ),
    allocated_storage=20,
    multi_az=False,
    deletion_protection=is_prod,
    removal_policy=RemovalPolicy.RETAIN if is_prod else RemovalPolicy.DESTROY,
    backup_retention=Duration.days(7 if is_prod else 1),
    storage_encrypted=True,
)
```

RDS PostgreSQL 15 defaults to `rds.force_ssl=1`, so connection URLs need
`?ssl=require` (handled by `app/config.py`).

Connection string stored in Secrets Manager automatically.

### ElastiCache Redis
```python
elasticache.CfnReplicationGroup(
    replication_group_id=f"worldcup-{env_name}",
    replication_group_description="worldcup-cache",
    num_cache_clusters=1,              # single node for our scale
    automatic_failover_enabled=False,  # REQUIRED with 1 node — defaults to on and fails deploy
    multi_az_enabled=False,
    cache_node_type="cache.t3.micro",
    engine="redis",
    engine_version="7.0",
    cache_subnet_group_name=subnet_group.cache_subnet_group_name,
    security_group_ids=[networking.redis_sg.security_group_id],
    at_rest_encryption_enabled=True,
    transit_encryption_enabled=True,   # clients must connect with rediss://
)
```

Outputs: RDS endpoint, Redis endpoint. The stack also exposes `redis_url`
(`rediss://{primary_endpoint}:{port}/0`) and `db_secret` for the ApiStack.

---

## `AuthStack`
File: `infrastructure/stacks/auth_stack.py`

### Cognito User Pool
```python
cognito.UserPool(
    user_pool_name=f"worldcup-{env_name}",
    self_sign_up_enabled=True,
    sign_in_aliases=cognito.SignInAliases(email=True, username=True),
    auto_verify=cognito.AutoVerifiedAttrs(email=True),
    standard_attributes=cognito.StandardAttributes(
        email=cognito.StandardAttribute(required=True, mutable=True),
    ),
    password_policy=cognito.PasswordPolicy(
        min_length=8,
        require_uppercase=True,
        require_digits=True,
        require_symbols=False,
    ),
    account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
    removal_policy=RemovalPolicy.RETAIN,  # never destroy on cdk destroy
)
```

### Cognito App Client
```python
user_pool.add_client(
    f"worldcup-{env_name}-client",
    auth_flows=cognito.AuthFlow(user_password=True, user_srp=True),
    generate_secret=False,  # SPA client, no secret
    access_token_validity=Duration.hours(1),
    id_token_validity=Duration.hours(1),
    refresh_token_validity=Duration.days(30),
)
```

Outputs: `user_pool_id`, `client_id`.

---

## `ApiStack`
File: `infrastructure/stacks/api_stack.py`

### Code bundling
One Docker-bundled asset shared by the API and ops functions (no Lambda layer).
Requires Docker running locally at synth time:
```python
code = lambda_.Code.from_asset(
    "../backend",
    exclude=[".venv", "venv", "**/__pycache__", ".pytest_cache", "tests", ".env"],
    bundling=BundlingOptions(
        image=lambda_.Runtime.PYTHON_3_12.bundling_image,
        command=["bash", "-c",
            "pip install -r requirements.txt -t /asset-output"
            " && cp -r app migrations alembic.ini"
            " worldcup2026_teams.json worldcup2026_matches.json /asset-output/"],
    ),
)
```
The bundle includes `migrations/` + the WC2026 JSON files so the ops Lambda can
run alembic and the data loaders.

### API Lambda Function (`worldcup-{env}-api`)
Handler `app.main.handler`, 512MB, 30s timeout, in the VPC private subnets with
`lambda_sg`. Environment:
```python
environment = {
    "DB_SECRET_ARN": data.db_secret.secret_arn,   # config.py builds DATABASE_URL from it
    "REDIS_URL": data.redis_url,                  # rediss://... (not secret)
    "COGNITO_USER_POOL_ID": auth.user_pool.user_pool_id,
    "COGNITO_CLIENT_ID": auth.client.user_pool_client_id,
    "COGNITO_REGION": self.region,
    "ENVIRONMENT": env_name,
    "ALLOWED_ORIGINS": '["https://{cloudfront_domain}","http://localhost:5173"]',
    "MOCK_AUTH": "false",
}
db_secret.grant_read(api_function)   # and the ops function
```

### Ops Lambda Function (`worldcup-{env}-ops`)
Same code asset + environment, handler `app.workers.ops.handler`, 512MB,
5 min timeout. Invoked manually via `scripts/migrate.sh` (see below).

### HTTP API Gateway
```python
apigw.HttpApi(
    api_name=f"worldcup-{env_name}-api",
    cors_preflight=apigw.CorsPreflightOptions(
        allow_origins=[f"https://{frontend.distribution_domain_name}", "http://localhost:5173"],
        allow_methods=[apigw.CorsHttpMethod.ANY],
        allow_headers=["Authorization", "Content-Type", "X-Dev-User-Id"],
        max_age=Duration.hours(1),
    ),
    default_integration=HttpLambdaIntegration("LambdaIntegration", api_function),
)
```

All routes proxy to Lambda via the default integration. The frontend calls the
API Gateway URL directly (baked into the Vite build) — there is no `/api/*`
CloudFront behavior.

Outputs: `api_url`, `ops_function_name`.

---

## `FrontendStack`
File: `infrastructure/stacks/frontend_stack.py`

### S3 Bucket
```python
s3.Bucket(
    block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
    removal_policy=RemovalPolicy.DESTROY,
    auto_delete_objects=True,
)
```
(No S3 website hosting — CloudFront reads the private bucket via Origin Access
Control.)

### CloudFront Distribution
```python
cloudfront.Distribution(
    default_behavior=cloudfront.BehaviorOptions(
        origin=origins.S3BucketOrigin.with_origin_access_control(bucket),
        viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
    ),
    default_root_object="index.html",
    error_responses=[
        # SPA fallback — S3 via OAC returns 403 (not 404) for unknown keys
        cloudfront.ErrorResponse(http_status=403, response_http_status=200,
                                 response_page_path="/index.html"),
        cloudfront.ErrorResponse(http_status=404, response_http_status=200,
                                 response_page_path="/index.html"),
    ],
)
```
No custom domain — the app is served from the default `*.cloudfront.net` domain
(prod: `deickez3ug2pm.cloudfront.net`).

Deploy step (after CDK synth — requires `../frontend/dist` to exist):
```python
s3deploy.BucketDeployment(
    sources=[s3deploy.Source.asset("../frontend/dist")],
    destination_bucket=bucket,
    distribution=distribution,
    distribution_paths=["/*"],  # invalidate on deploy
)
```

---

## Ops Lambda (replaces SyncStack)
Defined inside `ApiStack`. Same bundled code as the API Lambda but handler
`app.workers.ops.handler`, memory 512MB, timeout 5 minutes, same VPC +
security groups. Invoked manually via `scripts/migrate.sh`:

```bash
./scripts/migrate.sh prod                        # alembic upgrade head
./scripts/migrate.sh prod seed                   # load WC2026 teams + matches
./scripts/migrate.sh prod make_admin you@x.com   # grant admin
```

---

## Secrets Manager Entries
Auto-created by CDK (no manual secrets needed):
```
worldcup/{env}/db-admin    → {"username": "...", "password": "...", "host": "...", ...}
```
The Lambdas receive `DB_SECRET_ARN` and build `DATABASE_URL` from the secret
at cold start (`app/config.py`).

---

## CDK Deploy Commands
Prerequisites: Docker running, AWS profile `worldcup`, Node + `cdk` CLI,
Python venv at `infrastructure/.venv` with `requirements.txt` installed.
The account (967512078951/us-east-1) is already bootstrapped.

```bash
cd infrastructure
./scripts/deploy.sh prod     # full two-pass deploy (infra + frontend rebuild)
# or manually:
cdk deploy --all --context env=prod --profile worldcup
```

`deploy.sh` is two-pass because the Vite build needs the API URL + Cognito IDs
from the stack outputs: deploy everything → write `frontend/.env.production`
from `outputs-{env}.json` → `npm run build` → redeploy the frontend stack.

After a first deploy: `./scripts/migrate.sh prod` then
`./scripts/migrate.sh prod seed` (see `03_DATA_LOADING_SPEC.md`).

## Dev Environment (testing changes against live prod)

Every stack is parameterized by `env_name`, so a dev environment is a fully
isolated parallel copy (`worldcup-dev-*`) with its own RDS, Redis, Cognito pool,
and CloudFront — prod is never touched.

### Stand it up once
```bash
cd infrastructure
./scripts/setup-dev.sh dev          # deploy all stacks + migrate + seed (~15-20 min)
./scripts/migrate.sh dev make_admin you@example.com
```
The 15-20 min is RDS provisioning and only happens here (or after a destroy).

### Iterate fast (the normal per-test loop)
Leave networking + data + auth running and redeploy only code. `cdk deploy`
skips unchanged stacks, so RDS/Redis are never rebuilt and dev data persists:
```bash
./scripts/deploy-dev-code.sh dev              # backend only — ~2 min
./scripts/deploy-dev-code.sh dev --frontend   # frontend only (two-pass build)
./scripts/deploy-dev-code.sh dev --all        # both
```

### Decommission when done for a while
Dev costs ~$32/mo running (RDS $15 + Redis $12 + NAT $5 — these are coupled to
keeping RDS alive; the Lambda/API/S3/CloudFront parts are <$1). Tear it all down
to stop the cost (loses RDS data + Cognito accounts; next stand-up is ~15-20 min
again):
```bash
./scripts/destroy.sh dev
```
`destroy.sh` force-purges the `worldcup/dev/db-admin` secret — otherwise Secrets
Manager keeps it for a 7-day recovery window and a rebuild within that window
fails with "secret already scheduled for deletion". Dev's Cognito pool and RDS
use `RemovalPolicy.DESTROY` (prod uses `RETAIN`) so the teardown is clean.

> Tear-down is **not** a per-test step — only redeploy code between tests.
> Tearing down the stateless stacks saves <$1/mo but reintroduces the RDS wait.

## Cost Estimate (prod, ~50 users)
| Service | Monthly |
|---|---|
| RDS t3.micro (single AZ) | ~$15 |
| ElastiCache t3.micro | ~$12 |
| NAT Gateway | ~$5 |
| Lambda (API + ops) | <$1 |
| API Gateway | <$1 |
| CloudFront + S3 | <$1 |
| Cognito | Free |
| **Total** | **~$35** |
