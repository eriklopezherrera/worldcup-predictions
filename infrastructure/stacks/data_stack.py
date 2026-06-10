import aws_cdk as cdk
import aws_cdk.aws_rds as rds
import aws_cdk.aws_elasticache as elasticache
import aws_cdk.aws_ec2 as ec2
from constructs import Construct


class DataStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, vpc: ec2.Vpc, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.db_instance = rds.DatabaseInstance(
            self, "Postgres",
            engine=rds.DatabaseInstanceEngine.postgres(version=rds.PostgresEngineVersion.VER_15),
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MICRO),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            database_name="worldcuppredictions",
        )

        subnet_group = elasticache.CfnSubnetGroup(
            self, "CacheSubnetGroup",
            description="ElastiCache subnet group",
            subnet_ids=[s.subnet_id for s in vpc.private_subnets],
        )
        self.cache_cluster = elasticache.CfnCacheCluster(
            self, "Redis",
            cache_node_type="cache.t3.micro",
            engine="redis",
            num_cache_nodes=1,
            cache_subnet_group_name=subnet_group.ref,
        )
