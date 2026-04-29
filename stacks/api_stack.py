from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_dynamodb as dynamodb,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
)
from constructs import Construct


class ApiStack(Stack):
    """
    Stack koji kreira:
      - DynamoDB tabelu sa partition key (PK) i sort key (SK)
      - 3 Lambda funkcije (post_item, get_item, get_partition)
      - REST API Gateway sa 3 endpoint-a
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ---------- DynamoDB tabela ----------
        # PK = partition key (npr. "USER#123"), SK = sort key (npr. "ORDER#456")
        # PAY_PER_REQUEST = on-demand billing, ne treba kapacitet provisioning
        table = dynamodb.Table(
            self,
            "ItemsTable",
            table_name="ItemsTable",
            partition_key=dynamodb.Attribute(
                name="PK", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="SK", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            # DESTROY samo za dev/test - u produkciji koristiti RETAIN
            removal_policy=RemovalPolicy.DESTROY,
        )

        # ---------- Lambda funkcije ----------
        common_env = {"TABLE_NAME": table.table_name}

        post_item_fn = _lambda.Function(
            self,
            "PostItemFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("lambda_functions/post_item"),
            environment=common_env,
            timeout=Duration.seconds(10),
            memory_size=256,
        )

        get_item_fn = _lambda.Function(
            self,
            "GetItemFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("lambda_functions/get_item"),
            environment=common_env,
            timeout=Duration.seconds(10),
            memory_size=256,
        )

        get_partition_fn = _lambda.Function(
            self,
            "GetPartitionFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("lambda_functions/get_partition"),
            environment=common_env,
            timeout=Duration.seconds(15),
            memory_size=256,
        )

        # Least-privilege IAM permisije po funkciji
        table.grant_write_data(post_item_fn)
        table.grant_read_data(get_item_fn)
        table.grant_read_data(get_partition_fn)

        # ---------- API Gateway ----------
        api = apigw.RestApi(
            self,
            "ItemsApi",
            rest_api_name="ItemsApi",
            description="REST API za rad sa DynamoDB tabelom",
            deploy_options=apigw.StageOptions(stage_name="prod"),
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=["GET", "POST", "OPTIONS"],
                allow_headers=["Content-Type", "Authorization"],
            ),
        )

        # /items
        items_resource = api.root.add_resource("items")
        # POST /items  -> dodaje novi item
        items_resource.add_method("POST", apigw.LambdaIntegration(post_item_fn))

        # /items/{pk}  -> GET vraca celu particiju (sa paginacijom preko query stringa)
        pk_resource = items_resource.add_resource("{pk}")
        pk_resource.add_method("GET", apigw.LambdaIntegration(get_partition_fn))

        # /items/{pk}/{sk}  -> GET vraca jedan konkretan item
        sk_resource = pk_resource.add_resource("{sk}")
        sk_resource.add_method("GET", apigw.LambdaIntegration(get_item_fn))
