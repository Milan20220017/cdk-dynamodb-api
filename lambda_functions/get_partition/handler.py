"""
GET /items/{pk}?limit=20&nextToken=...
Vraća sve iteme iz jedne particije, sa paginacijom i detaljnim logama.
FIXED: Decimal konverzija za JSON
"""
import base64
import json
import os
import urllib.parse
import boto3
import logging
import traceback
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from datetime import datetime
from decimal import Decimal

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ.get("TABLE_NAME", "ItemsTable"))

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


def _to_json_serializable(obj):
    """Konvertuj DynamoDB Decimal tipove u JSON-friendly format"""
    if isinstance(obj, dict):
        return {k: _to_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_to_json_serializable(i) for i in obj]
    elif isinstance(obj, Decimal):
        return float(obj) if obj % 1 else int(obj)
    return obj


def _log(level: str, message: str, **kwargs):
    """Strukturirani log u JSON-u"""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "level": level,
        "message": message,
        **kwargs
    }
    print(json.dumps(log_entry))


def _response(status: int, body: dict, request_id: str = None) -> dict:
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
    }
    if request_id:
        headers["X-Request-ID"] = request_id
    
    return {
        "statusCode": status,
        "headers": headers,
        "body": json.dumps(body, default=str),
    }


def _encode_token(last_evaluated_key: dict) -> str:
    """DynamoDB LastEvaluatedKey -> base64 string za URL."""
    raw = json.dumps(last_evaluated_key, default=str).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8")


def _decode_token(token: str) -> dict:
    """Base64 token -> DynamoDB LastEvaluatedKey"""
    try:
        raw = base64.urlsafe_b64decode(token.encode("utf-8"))
        return json.loads(raw.decode("utf-8"))
    except Exception as e:
        _log("WARN", f"Invalid token decoding: {str(e)}", token=token[:50])
        raise ValueError(f"Invalid pagination token: {str(e)}")


def lambda_handler(event, context):
    """GET /items/{pk}?limit=20&nextToken=... — čitanje particije sa paginacijom"""
    
    request_id = context.aws_request_id
    
    _log("INFO", "GET /items/{pk} request started",
         request_id=request_id,
         function_name=context.function_name,
         remaining_time_ms=context.get_remaining_time_in_millis())
    
    # ==================== FAZA 1: Ekstraktovanje path i query parametara ====================
    
    try:
        path_params = event.get("pathParameters") or {}
        pk = path_params.get("pk")
        
        if not pk:
            error_msg = "Missing pk in path"
            _log("WARN", error_msg, request_id=request_id)
            return _response(400, {"error": error_msg}, request_id=request_id)
        
        # Path parametar je URL-encoded
        pk = urllib.parse.unquote(pk)
        _log("DEBUG", "PK decoded", pk=pk, request_id=request_id)

    except Exception as e:
        error_msg = f"Error processing path parameters: {str(e)}"
        _log("ERROR", error_msg,
             error=str(e), traceback=traceback.format_exc(),
             request_id=request_id)
        return _response(400, {"error": error_msg}, request_id=request_id)

    # ==================== FAZA 2: Parsiranje query parametara ====================
    
    try:
        qs = event.get("queryStringParameters") or {}
        
        # Limit
        try:
            limit = int(qs.get("limit", DEFAULT_LIMIT))
        except ValueError:
            error_msg = "limit must be an integer"
            _log("WARN", error_msg,
                 limit_value=qs.get("limit"),
                 request_id=request_id)
            return _response(400, {"error": error_msg}, request_id=request_id)
        
        # Limit boundaries
        if limit < 1:
            limit = 1
        elif limit > MAX_LIMIT:
            limit = MAX_LIMIT
        
        _log("DEBUG", "Query parameters parsed",
             limit=limit, has_next_token=bool(qs.get("nextToken")),
             request_id=request_id)

    except Exception as e:
        error_msg = f"Error processing query parameters: {str(e)}"
        _log("ERROR", error_msg,
             error=str(e), traceback=traceback.format_exc(),
             request_id=request_id)
        return _response(400, {"error": error_msg}, request_id=request_id)

    # ==================== FAZA 3: Построј DynamoDB query ====================
    
    try:
        query_kwargs = {
            "KeyConditionExpression": Key("PK").eq(pk),
            "Limit": limit,
        }
        
        # Paginacijski token (ako postoji)
        next_token = qs.get("nextToken")
        if next_token:
            try:
                exclusive_start_key = _decode_token(next_token)
                query_kwargs["ExclusiveStartKey"] = exclusive_start_key
                _log("DEBUG", "Pagination token decoded and set",
                     pk=pk, limit=limit,
                     request_id=request_id)
            except ValueError as e:
                error_msg = f"Invalid pagination token: {str(e)}"
                _log("WARN", error_msg, request_id=request_id)
                return _response(400, {"error": error_msg}, request_id=request_id)
        else:
            _log("DEBUG", "First page request",
                 pk=pk, limit=limit, request_id=request_id)

    except Exception as e:
        error_msg = f"Error building query: {str(e)}"
        _log("ERROR", error_msg,
             error=str(e), traceback=traceback.format_exc(),
             request_id=request_id)
        return _response(400, {"error": error_msg}, request_id=request_id)

    # ==================== FAZA 4: Izvršavanje DynamoDB query ====================
    
    try:
        _log("INFO", "Executing DynamoDB query",
             pk=pk, limit=limit,
             has_pagination_token=bool(next_token),
             request_id=request_id)
        
        result = table.query(**query_kwargs)
        
        _log("DEBUG", "DynamoDB query completed",
             items_returned=result.get("Count", 0),
             items_scanned=result.get("ScannedCount", 0),
             has_more_items="LastEvaluatedKey" in result,
             request_id=request_id)

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        
        _log("ERROR", f"DynamoDB ClientError: {error_code}",
             error_code=error_code,
             error_message=error_msg,
             pk=pk,
             request_id=request_id)
        
        return _response(500, {"error": f"Database error: {error_code}"}, request_id=request_id)

    except Exception as e:
        _log("ERROR", "Unexpected error during query",
             error=str(e),
             error_type=type(e).__name__,
             traceback=traceback.format_exc(),
             pk=pk,
             request_id=request_id)
        
        return _response(500, {"error": "Internal server error"}, request_id=request_id)

    # ==================== FAZA 5: Konverzija Decimal tipova ====================
    
    try:
        items = result.get("Items", [])
        items_json = _to_json_serializable(items)
        _log("DEBUG", "Items converted to JSON-serializable format",
             pk=pk, items_count=len(items),
             request_id=request_id)
    except Exception as e:
        _log("ERROR", "Error converting items to JSON",
             error=str(e),
             traceback=traceback.format_exc(),
             request_id=request_id)
        return _response(500, {"error": "Error processing items"}, request_id=request_id)

    # ==================== FAZA 6: Formatiranje odgovora ====================
    
    try:
        count = result.get("Count", 0)
        
        response_body = {
            "items": items_json,
            "count": count,
        }
        
        # Ako ima više podataka, dodaj nextToken
        if "LastEvaluatedKey" in result:
            next_token_str = _encode_token(result["LastEvaluatedKey"])
            response_body["nextToken"] = next_token_str
            _log("DEBUG", "Next page token generated",
                 pk=pk, items_in_page=count,
                 request_id=request_id)
        else:
            _log("DEBUG", "Last page of results",
                 pk=pk, items_in_page=count,
                 request_id=request_id)

    except Exception as e:
        error_msg = f"Error formatting response: {str(e)}"
        _log("ERROR", error_msg,
             error=str(e), traceback=traceback.format_exc(),
             request_id=request_id)
        return _response(500, {"error": error_msg}, request_id=request_id)

    # ==================== FAZA 7: Uspešan odgovor ====================
    
    _log("INFO", "GET /items/{pk} completed successfully",
         pk=pk,
         items_returned=count,
         has_next_page="nextToken" in response_body,
         response_size=len(json.dumps(response_body, default=str)),
         status_code=200,
         request_id=request_id)
    
    return _response(200, response_body, request_id=request_id)