import aws_cdk as cdk

from stacks.networking_stack import NetworkingStack
from stacks.data_stack import DataStack
from stacks.auth_stack import AuthStack
from stacks.api_stack import ApiStack
from stacks.frontend_stack import FrontendStack
from stacks.sync_stack import SyncStack

app = cdk.App()

env = cdk.Environment(account=app.node.try_get_context("account"), region="us-east-1")

networking = NetworkingStack(app, "NetworkingStack", env=env)
data = DataStack(app, "DataStack", vpc=networking.vpc, env=env)
auth = AuthStack(app, "AuthStack", env=env)
api = ApiStack(app, "ApiStack", vpc=networking.vpc, db=data.db_instance, cache=data.cache_cluster, user_pool=auth.user_pool, env=env)
frontend = FrontendStack(app, "FrontendStack", api_url=api.api_url, env=env)
sync = SyncStack(app, "SyncStack", vpc=networking.vpc, db=data.db_instance, env=env)

app.synth()
