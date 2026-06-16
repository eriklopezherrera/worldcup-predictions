from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from constructs import Construct

# The app entry points: never cache-locked so a new deploy is always picked up
# on the next load. Everything else (hashed /assets bundles, workbox, icons) is
# content-hashed or stable and can be cached immutably.
NO_CACHE_FILES = [
    "index.html",
    "sw.js",
    "registerSW.js",
    "manifest.json",
    "manifest.webmanifest",
]


class FrontendStack(Stack):
    """S3 + CloudFront hosting for the React PWA.

    Independent of the other stacks: the API URL and Cognito IDs are baked
    into the Vite build (see scripts/deploy.sh), not into this stack.
    """

    def __init__(self, scope: Construct, construct_id: str, *, env_name: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        bucket = s3.Bucket(
            self,
            "SiteBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        distribution = cloudfront.Distribution(
            self,
            "Distribution",
            comment=f"worldcup-{env_name} frontend",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
            ),
            default_root_object="index.html",
            error_responses=[
                # SPA fallback: S3 via OAC returns 403 for unknown paths.
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                ),
            ],
        )

        # Two passes so each file class gets the right Cache-Control. prune is off
        # on both: old hashed bundles are left in place so a user still running the
        # previous index.html (cached in their SW) doesn't hit 404s mid-rollout.
        s3deploy.BucketDeployment(
            self,
            "DeployAssets",
            sources=[s3deploy.Source.asset("../frontend/dist")],
            destination_bucket=bucket,
            exclude=NO_CACHE_FILES,
            prune=False,
            cache_control=[
                s3deploy.CacheControl.set_public(),
                s3deploy.CacheControl.max_age(Duration.days(365)),
                s3deploy.CacheControl.immutable(),
            ],
        )
        s3deploy.BucketDeployment(
            self,
            "DeployEntrypoints",
            sources=[s3deploy.Source.asset("../frontend/dist")],
            destination_bucket=bucket,
            exclude=["*"],
            include=NO_CACHE_FILES,
            prune=False,
            cache_control=[s3deploy.CacheControl.no_cache(), s3deploy.CacheControl.must_revalidate()],
            distribution=distribution,
            distribution_paths=[f"/{name}" for name in NO_CACHE_FILES],  # invalidate entry points on deploy
        )

        self.distribution_domain_name = distribution.distribution_domain_name

        CfnOutput(self, "FrontendUrl", value=f"https://{self.distribution_domain_name}")
