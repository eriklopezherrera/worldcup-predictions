import aws_cdk as cdk
import aws_cdk.aws_lambda as lambda_
import aws_cdk.aws_events as events
import aws_cdk.aws_events_targets as targets
import aws_cdk.aws_ec2 as ec2
from constructs import Construct


class SyncStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, vpc: ec2.Vpc, db, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        sync_fn = lambda_.Function(
            self, "SyncWorker",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="app.workers.sync_worker.handler",
            code=lambda_.Code.from_asset("../backend"),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            memory_size=256,
            timeout=cdk.Duration.minutes(5),
        )

        rule = events.Rule(
            self, "SyncSchedule",
            schedule=events.Schedule.rate(cdk.Duration.minutes(5)),
        )
        rule.add_target(targets.LambdaFunction(sync_fn))
