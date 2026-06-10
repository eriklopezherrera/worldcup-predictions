from aws_cdk import BundlingOptions, CfnOutput, Duration, Stack
from aws_cdk import aws_apigatewayv2 as apigw
from aws_cdk import aws_apigatewayv2_integrations as integrations
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from constructs import Construct

from stacks.auth_stack import AuthStack
from stacks.data_stack import DataStack
from stacks.networking_stack import NetworkingStack


class ApiStack(Stack):
    """API Lambda + HTTP API Gateway, plus the ops Lambda (migrations/seed)."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        env_name: str,
        networking: NetworkingStack,
        data: DataStack,
        auth: AuthStack,
        frontend_domain: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        frontend_origin = f"https://{frontend_domain}"
        allowed_origins = [frontend_origin, "http://localhost:5173"]

        # One bundled asset (deps + app + migrations + WC2026 data) shared by
        # both functions. Requires Docker locally.
        code = lambda_.Code.from_asset(
            "../backend",
            exclude=[".venv", "venv", "**/__pycache__", ".pytest_cache", "tests", ".env"],
            bundling=BundlingOptions(
                image=lambda_.Runtime.PYTHON_3_12.bundling_image,
                command=[
                    "bash",
                    "-c",
                    "pip install -r requirements.txt -t /asset-output"
                    " && cp -r app migrations alembic.ini"
                    " worldcup2026_teams.json worldcup2026_matches.json /asset-output/",
                ],
            ),
        )

        environment = {
            "DB_SECRET_ARN": data.db_secret.secret_arn,
            "REDIS_URL": data.redis_url,
            "COGNITO_USER_POOL_ID": auth.user_pool.user_pool_id,
            "COGNITO_CLIENT_ID": auth.client.user_pool_client_id,
            "COGNITO_REGION": self.region,
            "ENVIRONMENT": env_name,
            "ALLOWED_ORIGINS": '["' + '","'.join(allowed_origins) + '"]',
            "MOCK_AUTH": "false",
        }
        vpc_props = dict(
            vpc=networking.vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            security_groups=[networking.lambda_sg],
        )

        api_function = lambda_.Function(
            self,
            "ApiFunction",
            function_name=f"worldcup-{env_name}-api",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="app.main.handler",
            code=code,
            timeout=Duration.seconds(30),
            memory_size=512,
            environment=environment,
            **vpc_props,
        )

        # Invoked manually for alembic migrations, WC2026 data load, make_admin.
        self.ops_function = lambda_.Function(
            self,
            "OpsFunction",
            function_name=f"worldcup-{env_name}-ops",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="app.workers.ops.handler",
            code=code,
            timeout=Duration.minutes(5),
            memory_size=512,
            environment=environment,
            **vpc_props,
        )

        for fn in (api_function, self.ops_function):
            data.db_secret.grant_read(fn)
            fn.add_to_role_policy(
                iam.PolicyStatement(
                    actions=[
                        "cognito-idp:DescribeUserPool",
                        "cognito-idp:DescribeUserPoolClient",
                    ],
                    resources=[auth.user_pool.user_pool_arn],
                )
            )

        http_api = apigw.HttpApi(
            self,
            "HttpApi",
            api_name=f"worldcup-{env_name}-api",
            cors_preflight=apigw.CorsPreflightOptions(
                allow_origins=allowed_origins,
                allow_methods=[apigw.CorsHttpMethod.ANY],
                allow_headers=["Authorization", "Content-Type", "X-Dev-User-Id"],
                max_age=Duration.hours(1),
            ),
            default_integration=integrations.HttpLambdaIntegration(
                "LambdaIntegration", api_function
            ),
        )

        self.api_url = http_api.api_endpoint

        CfnOutput(self, "ApiUrl", value=self.api_url)
        CfnOutput(self, "OpsFunctionName", value=self.ops_function.function_name)
