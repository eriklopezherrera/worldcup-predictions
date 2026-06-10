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
    └── AuthStack (independent)
         └── ApiStack (needs VPC, DB, Redis, Cognito)
         └── SyncStack (needs VPC, DB, API key)
              └── FrontendStack (needs API Gateway URL)
```

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

**For dev environment:** use only 1 AZ, 1 NAT Gateway to reduce cost.

---

## `DataStack`
File: `infrastructure/stacks/data_stack.py`

### RDS PostgreSQL
```python
rds.DatabaseInstance(
    engine=rds.DatabaseInstanceEngine.postgres(version=rds.PostgresEngineVersion.VER_15),
    instance_type=ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MICRO),
    vpc=networking.vpc,
    vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
    security_groups=[networking.rds_sg],
    database_name="worldcuppredictions",
    credentials=rds.Credentials.from_generated_secret("db-admin"),
    deletion_protection=True,         # prod only
    backup_retention=Duration.days(7),
    storage_encrypted=True,
)
```

Connection string stored in Secrets Manager automatically.

### ElastiCache Redis
```python
elasticache.CfnReplicationGroup(
    replication_group_description="worldcup-cache",
    num_cache_clusters=1,             # single node for our scale
    cache_node_type="cache.t3.micro",
    engine="redis",
    engine_version="7.0",
    subnet_group_name=subnet_group.ref,
    security_group_ids=[networking.redis_sg.security_group_id],
    at_rest_encryption_enabled=True,
    transit_encryption_enabled=True,
)
```

Outputs: RDS endpoint, Redis endpoint.

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

### Lambda Layer (dependencies)
```python
# Build Lambda layer from backend/requirements.txt
layer = lambda_.LayerVersion(
    code=lambda_.Code.from_docker_build(
        path="../backend",
        build_args={"PLATFORM": "linux/amd64"},
    ),
    compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
)
```

### API Lambda Function
```python
api_function = lambda_.Function(
    runtime=lambda_.Runtime.PYTHON_3_12,
    handler="app.main.handler",
    code=lambda_.Code.from_asset("../backend", 
        bundling=BundlingOptions(
            image=lambda_.Runtime.PYTHON_3_12.bundling_image,
            command=["bash", "-c", "pip install -r requirements.txt -t /asset-output && cp -r app /asset-output/"]
        )
    ),
    vpc=networking.vpc,
    vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
    security_groups=[networking.lambda_sg],
    timeout=Duration.seconds(30),
    memory_size=512,
    environment={
        "DATABASE_URL": f"postgresql+asyncpg://...",   # from secret
        "REDIS_URL": f"rediss://...",                  # from secret
        "COGNITO_USER_POOL_ID": auth.user_pool.user_pool_id,
        "COGNITO_CLIENT_ID": auth.client.user_pool_client_id,
        "COGNITO_REGION": self.region,
        "ENVIRONMENT": env_name,
        "ALLOWED_ORIGINS": "https://yourdomain.com",
    }
)

# Grant Lambda access to secrets
db_secret.grant_read(api_function)
football_api_secret.grant_read(api_function)
```

### HTTP API Gateway
```python
apigw.HttpApi(
    cors_preflight=apigw.CorsPreflightOptions(
        allow_origins=["https://yourdomain.com", "http://localhost:5173"],
        allow_methods=[apigw.CorsHttpMethod.ANY],
        allow_headers=["Authorization", "Content-Type"],
        max_age=Duration.hours(1),
    ),
    default_integration=HttpLambdaIntegration("LambdaIntegration", api_function),
)
```

All routes proxy to Lambda (catch-all `/{proxy+}`).

Outputs: `api_url`.

---

## `FrontendStack`
File: `infrastructure/stacks/frontend_stack.py`

### S3 Bucket
```python
s3.Bucket(
    website_index_document="index.html",
    website_error_document="index.html",  # React Router needs this
    block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
    removal_policy=RemovalPolicy.DESTROY,
    auto_delete_objects=True,
)
```

### CloudFront Distribution
```python
cloudfront.Distribution(
    default_behavior=cloudfront.BehaviorOptions(
        origin=origins.S3Origin(bucket, origin_access_identity=oai),
        viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
    ),
    additional_behaviors={
        "/api/*": cloudfront.BehaviorOptions(
            origin=origins.HttpOrigin(api_domain),
            cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
            allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
            origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
        )
    },
    default_root_object="index.html",
    error_responses=[
        cloudfront.ErrorResponse(
            http_status=404,
            response_http_status=200,
            response_page_path="/index.html",  # SPA fallback
        )
    ],
    domain_names=["yourdomain.com"],        # optional custom domain
    certificate=acm_cert,                   # optional ACM cert
)
```

Deploy step (after CDK synth):
```python
s3deploy.BucketDeployment(
    sources=[s3deploy.Source.asset("../frontend/dist")],
    destination_bucket=bucket,
    distribution=distribution,
    distribution_paths=["/*"],  # invalidate on deploy
)
```

---

## `SyncStack`
File: `infrastructure/stacks/sync_stack.py`

### Sync Lambda
Same bundling as API Lambda but handler: `app.workers.sync_worker.handler`.
Memory: 256MB, Timeout: 5 minutes.
Same VPC + security groups.

### EventBridge Rules
```python
# Fixture sync: daily at 06:00 UTC
events.Rule(
    schedule=events.Schedule.cron(hour="6", minute="0"),
    targets=[targets.LambdaFunction(sync_function, 
        event=events.RuleTargetInput.from_object({"sync_type": "fixtures"})
    )],
)

# Score sync: every 3 minutes during tournament
events.Rule(
    schedule=events.Schedule.rate(Duration.minutes(3)),
    enabled=True,  # set to False outside tournament dates
    targets=[targets.LambdaFunction(sync_function,
        event=events.RuleTargetInput.from_object({"sync_type": "scores"})
    )],
)
```

---

## Secrets Manager Entries
Manually create before first deploy:
```
/worldcup/{env}/football-api-key    → {"api_key": "xxxxx"}
```

Auto-created by CDK:
```
/worldcup/{env}/db-admin            → {"username": "...", "password": "...", "host": "...", ...}
```

---

## CDK Deploy Commands
```bash
cd infrastructure
pip install -r requirements.txt
cdk bootstrap aws://ACCOUNT_ID/us-east-1    # first time only
cdk deploy --all --context env=prod
```

## Cost Estimate (prod, ~50 users)
| Service | Monthly |
|---|---|
| RDS t3.micro (single AZ) | ~$15 |
| ElastiCache t3.micro | ~$12 |
| NAT Gateway | ~$5 |
| Lambda (API + sync) | <$1 |
| API Gateway | <$1 |
| CloudFront + S3 | <$1 |
| Cognito | Free |
| EventBridge | Free |
| **Total** | **~$35** |
