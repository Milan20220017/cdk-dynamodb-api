"""
POST /items
Body (JSON): { "PK": "...", "SK": "...", ...bilo koji ostali atributi }
Cuva item u DynamoDB tabeli.
"""
import json
import os
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
    # API Gateway proxy integration salje body kao string
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _response(400, {"error": "Invalid JSON body"})

    if not isinstance(body, dict):
        return _response(400, {"error": "Body must be a JSON object"})

    # Validacija - PK i SK su obavezni
    pk = body.get("PK")
    sk = body.get("SK")
    if not pk or not sk:
        return _response(400, {"error": "PK and SK are required"})

    # Item moze imati bilo koje dodatne atribute - samo ga prosledjujemo
    try:
        table.put_item(Item=body)
    except ClientError as e:
        return _response(500, {"error": str(e)})

    return _response(201, {"message": "Item created", "item": body})
