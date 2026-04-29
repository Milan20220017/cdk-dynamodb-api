"""
GET /items/{pk}?limit=20&nextToken=...
Vraca sve iteme iz jedne particije, sa paginacijom.

Paginacija:
  - klijent salje ?limit=N (opciono) i ?nextToken=... (opciono)
  - response sadrzi 'nextToken' ako postoji jos podataka
  - klijent prosledjuje taj token u sledecem zahtevu
"""
import base64
import json
import os
import urllib.parse
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


def _response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body, default=str),
    }


def _encode_token(last_evaluated_key: dict) -> str:
    """DynamoDB LastEvaluatedKey -> base64 string za URL."""
    raw = json.dumps(last_evaluated_key).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8")


def _decode_token(token: str) -> dict:
    raw = base64.urlsafe_b64decode(token.encode("utf-8"))
    return json.loads(raw.decode("utf-8"))


def lambda_handler(event, context):
    path_params = event.get("pathParameters") or {}
    pk = path_params.get("pk")
    if not pk:
        return _response(400, {"error": "Missing pk in path"})
    pk = urllib.parse.unquote(pk)

    qs = event.get("queryStringParameters") or {}

    # parsiranje limita
    try:
        limit = int(qs.get("limit", DEFAULT_LIMIT))
    except ValueError:
        return _response(400, {"error": "limit must be an integer"})
    limit = max(1, min(limit, MAX_LIMIT))

    # parsiranje paginacionog tokena
    query_kwargs = {
        "KeyConditionExpression": Key("PK").eq(pk),
        "Limit": limit,
    }
    next_token = qs.get("nextToken")
    if next_token:
        try:
            query_kwargs["ExclusiveStartKey"] = _decode_token(next_token)
        except Exception:
            return _response(400, {"error": "Invalid nextToken"})

    try:
        result = table.query(**query_kwargs)
    except ClientError as e:
        return _response(500, {"error": str(e)})

    body = {
        "items": result.get("Items", []),
        "count": result.get("Count", 0),
    }
    # ako postoji LastEvaluatedKey -> ima jos podataka
    if "LastEvaluatedKey" in result:
        body["nextToken"] = _encode_token(result["LastEvaluatedKey"])

    return _response(200, body)
