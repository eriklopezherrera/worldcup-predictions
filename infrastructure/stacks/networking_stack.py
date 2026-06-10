import aws_cdk as cdk
import aws_cdk.aws_ec2 as ec2
from constructs import Construct


class NetworkingStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.vpc = ec2.Vpc(self, "Vpc", max_azs=2, nat_gateways=1)
