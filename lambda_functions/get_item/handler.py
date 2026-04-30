"""
GET /items/{pk}/{sk}
Vraca jedan konkretan item iz DynamoDB tabele sa detaljnim logama.
FIXED: Decimal konverzija za JSON
"""
import json
import os
import urllib.parse
import boto3
import logging
import traceback
from botocore.exceptions import ClientError
from datetime import datetime
from decimal import Decimal

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ.get("TABLE_NAME", "ItemsTable"))


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


def lambda_handler(event, context):
    """GET /items/{pk}/{sk} — čitanje pojedinačnog itema"""
    
    request_id = context.aws_request_id
    
    _log("INFO", "GET /items/{pk}/{sk} request started",
         request_id=request_id,
         function_name=context.function_name,
         remaining_time_ms=context.get_remaining_time_in_millis())
    
    # ==================== FAZA 1: Ekstraktovanje path parametara ====================
    
    try:
        path_params = event.get("pathParameters") or {}
        pk = path_params.get("pk")
        sk = path_params.get("sk")
        
        _log("DEBUG", "Path parameters received",
             pk_raw=pk, sk_raw=sk, request_id=request_id)
        
        if not pk or not sk:
            error_msg = "Missing pk or sk in path"
            _log("WARN", error_msg,
                 pk_present=bool(pk), sk_present=bool(sk),
                 request_id=request_id)
            return _response(400, {"error": error_msg}, request_id=request_id)

        # Path parametri su URL-encoded (npr. USER%23123 -> USER#123)
        pk = urllib.parse.unquote(pk)
        sk = urllib.parse.unquote(sk)
        
        _log("DEBUG", "Path parameters decoded",
             pk=pk, sk=sk, request_id=request_id)

    except Exception as e:
        error_msg = f"Error processing path parameters: {str(e)}"
        _log("ERROR", error_msg,
             error=str(e), traceback=traceback.format_exc(),
             request_id=request_id)
        return _response(400, {"error": error_msg}, request_id=request_id)

    # ==================== FAZA 2: Čitanje iz baze ====================
    
    try:
        _log("INFO", "Attempting to read item from DynamoDB",
             pk=pk, sk=sk, request_id=request_id)
        
        result = table.get_item(Key={"PK": pk, "SK": sk})
        
        _log("DEBUG", "DynamoDB query completed",
             response_keys=list(result.keys()),
             item_exists="Item" in result,
             request_id=request_id)

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        
        _log("ERROR", f"DynamoDB ClientError: {error_code}",
             error_code=error_code,
             error_message=error_msg,
             pk=pk, sk=sk,
             request_id=request_id)
        
        return _response(500, {"error": f"Database error: {error_code}"}, request_id=request_id)

    except Exception as e:
        _log("ERROR", "Unexpected error during item read",
             error=str(e),
             error_type=type(e).__name__,
             traceback=traceback.format_exc(),
             pk=pk, sk=sk,
             request_id=request_id)
        
        return _response(500, {"error": "Internal server error"}, request_id=request_id)

    # ==================== FAZA 3: Provera rezultata ====================
    
    item = result.get("Item")
    
    if not item:
        _log("WARN", "Item not found in DynamoDB",
             pk=pk, sk=sk, request_id=request_id)
        return _response(404, {"error": "Item not found"}, request_id=request_id)

    # ==================== FAZA 4: Konverzija Decimal tipova ====================
    
    try:
        item_json = _to_json_serializable(item)
        _log("DEBUG", "Item converted to JSON-serializable format",
             pk=pk, sk=sk, request_id=request_id)
    except Exception as e:
        _log("ERROR", "Error converting item to JSON",
             error=str(e),
             traceback=traceback.format_exc(),
             request_id=request_id)
        return _response(500, {"error": "Error processing item"}, request_id=request_id)

    # ==================== FAZA 5: Uspešan odgovor ====================
    
    _log("INFO", "Item successfully retrieved",
         pk=pk, sk=sk,
         attributes_count=len(item),
         response_size=len(json.dumps(item_json)),
         status_code=200,
         request_id=request_id)
    
    return _response(200, {"item": item_json}, request_id=request_id)