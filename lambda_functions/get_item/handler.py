"""
GET /items/{pk}/{sk}
Vraca jedan konkretan item iz DynamoDB tabele.
"""
import json
import os
import urllib.parse
import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])


def _response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body, default=str),
    }


def lambda_handler(event, context):
    path_params = event.get("pathParameters") or {}
    pk = path_params.get("pk")
    sk = path_params.get("sk")

    if not pk or not sk:
        return _response(400, {"error": "Missing pk or sk in path"})

    # Path parametri su URL-encoded (npr. USER%23123 -> USER#123)
    pk = urllib.parse.unquote(pk)
    sk = urllib.parse.unquote(sk)

    try:
        result = table.get_item(Key={"PK": pk, "SK": sk})
    except ClientError as e:
        return _response(500, {"error": str(e)})

    item = result.get("Item")
    if not item:
        return _response(404, {"error": "Item not found"})

    return _response(200, {"item": item})
