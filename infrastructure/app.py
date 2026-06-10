import os

import aws_cdk as cdk

from stacks.api_stack import ApiStack
from stacks.auth_stack import AuthStack
from stacks.data_stack import DataStack
from stacks.frontend_stack import FrontendStack
from stacks.networking_stack import NetworkingStack

app = cdk.App()

env_name = app.node.try_get_context("env") or "dev"
if env_name not in ("dev", "staging", "prod"):
    raise ValueError(f"Invalid env context: {env_name!r} (expected dev|staging|prod)")

# Account/region come from the active AWS profile — never hardcoded.
env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=os.environ.get("CDK_DEFAULT_REGION"),
)

networking = NetworkingStack(
    app, f"worldcup-{env_name}-networking", env_name=env_name, env=env
)
data = DataStack(
    app, f"worldcup-{env_name}-data", env_name=env_name, networking=networking, env=env
)
auth = AuthStack(app, f"worldcup-{env_name}-auth", env_name=env_name, env=env)

# Frontend hosting is independent; the API stack needs its CloudFront domain
# for CORS, and the Vite build (deploy.sh) bakes in the API URL + Cognito IDs.
frontend = FrontendStack(app, f"worldcup-{env_name}-frontend", env_name=env_name, env=env)

api = ApiStack(
    app,
    f"worldcup-{env_name}-api",
    env_name=env_name,
    networking=networking,
    data=data,
    auth=auth,
    frontend_domain=frontend.distribution_domain_name,
    env=env,
)

app.synth()
