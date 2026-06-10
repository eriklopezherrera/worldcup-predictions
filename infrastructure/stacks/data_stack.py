from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_elasticache as elasticache
from aws_cdk import aws_rds as rds
from constructs import Construct

from stacks.networking_stack import NetworkingStack


class DataStack(Stack):
    """RDS PostgreSQL + ElastiCache Redis."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        env_name: str,
        networking: NetworkingStack,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        is_prod = env_name == "prod"

        self.db_instance = rds.DatabaseInstance(
            self,
            "Postgres",
            instance_identifier=f"worldcup-{env_name}",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.of("15", "15")
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.T3, ec2.InstanceSize.MICRO
            ),
            vpc=networking.vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
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
        # Connection secret (username/password/host/port/dbname) managed by RDS.
        self.db_secret = self.db_instance.secret

        subnet_group = elasticache.CfnSubnetGroup(
            self,
            "CacheSubnetGroup",
            cache_subnet_group_name=f"worldcup-{env_name}-cache",
            description="ElastiCache subnet group",
            subnet_ids=[s.subnet_id for s in networking.vpc.private_subnets],
        )

        self.cache = elasticache.CfnReplicationGroup(
            self,
            "Redis",
            replication_group_id=f"worldcup-{env_name}",
            replication_group_description="worldcup-cache",
            num_cache_clusters=1,
            automatic_failover_enabled=False,  # single node — failover needs >=2
            multi_az_enabled=False,
            cache_node_type="cache.t3.micro",
            engine="redis",
            engine_version="7.0",
            cache_subnet_group_name=subnet_group.cache_subnet_group_name,
            security_group_ids=[networking.redis_sg.security_group_id],
            at_rest_encryption_enabled=True,
            transit_encryption_enabled=True,
        )
        self.cache.add_dependency(subnet_group)

        # rediss:// because transit encryption is enabled.
        self.redis_url = (
            f"rediss://{self.cache.attr_primary_end_point_address}"
            f":{self.cache.attr_primary_end_point_port}/0"
        )

        CfnOutput(self, "RdsEndpoint", value=self.db_instance.db_instance_endpoint_address)
        CfnOutput(self, "RedisEndpoint", value=self.cache.attr_primary_end_point_address)
