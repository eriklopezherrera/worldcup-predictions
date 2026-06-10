from aws_cdk import Stack
from aws_cdk import aws_ec2 as ec2
from constructs import Construct


class NetworkingStack(Stack):
    """VPC, subnets, and security groups shared by all other stacks."""

    def __init__(self, scope: Construct, construct_id: str, *, env_name: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # 2 AZs (RDS subnet groups require two even for single-AZ instances);
        # a single NAT gateway is enough at this scale.
        self.vpc = ec2.Vpc(
            self,
            "Vpc",
            vpc_name=f"worldcup-{env_name}",
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
            ],
        )

        self.lambda_sg = ec2.SecurityGroup(
            self,
            "LambdaSg",
            vpc=self.vpc,
            security_group_name=f"worldcup-{env_name}-lambda",
            description="API + ops Lambda functions",
            allow_all_outbound=False,
        )
        self.rds_sg = ec2.SecurityGroup(
            self,
            "RdsSg",
            vpc=self.vpc,
            security_group_name=f"worldcup-{env_name}-rds",
            description="RDS PostgreSQL",
            allow_all_outbound=False,
        )
        self.redis_sg = ec2.SecurityGroup(
            self,
            "RedisSg",
            vpc=self.vpc,
            security_group_name=f"worldcup-{env_name}-redis",
            description="ElastiCache Redis",
            allow_all_outbound=False,
        )

        # Lambda egress: HTTPS (Cognito, Secrets Manager), RDS, Redis. DNS to
        # the Amazon-provided resolver bypasses security group evaluation.
        self.lambda_sg.add_egress_rule(
            ec2.Peer.any_ipv4(), ec2.Port.tcp(443), "HTTPS to AWS APIs"
        )
        self.lambda_sg.add_egress_rule(self.rds_sg, ec2.Port.tcp(5432), "PostgreSQL")
        self.lambda_sg.add_egress_rule(self.redis_sg, ec2.Port.tcp(6379), "Redis")

        self.rds_sg.add_ingress_rule(self.lambda_sg, ec2.Port.tcp(5432), "From Lambda")
        self.redis_sg.add_ingress_rule(self.lambda_sg, ec2.Port.tcp(6379), "From Lambda")
