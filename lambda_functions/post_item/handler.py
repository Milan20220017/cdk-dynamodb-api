"""
POST /items
Body (JSON): { "PK": "...", "SK": "...", ...bilo koji ostali atributi }
Čuva item u DynamoDB tabeli sa detaljnim logama.
"""
import json
import os
import boto3
import logging
import traceback
from botocore.exceptions import ClientError
from datetime import datetime

# CloudWatch logger sa JSON format-om
logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ.get("TABLE_NAME", "ItemsTable"))


def _log(level: str, message: str, **kwargs):
    """Strukturirani log u JSON-u za lakšeg parsiranja"""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "level": level,
        "message": message,
        **kwargs
    }
    print(json.dumps(log_entry))


def _response(status: int, body: dict, request_id: str = None) -> dict:
    """HTTP odgovor sa headerima"""
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
    """POST /items — upisivanje novog itema u DynamoDB"""
    
    request_id = context.aws_request_id
    
    _log("INFO", "POST /items request started", 
         request_id=request_id,
         function_name=context.function_name,
         remaining_time_ms=context.get_remaining_time_in_millis())
    
    # ==================== FAZA 1: Parsiranje body-ja ====================
    
    try:
        body_raw = event.get("body") or "{}"
        _log("DEBUG", "Raw body received", body=body_raw[:200])  # First 200 chars
        
        body = json.loads(body_raw)
        _log("DEBUG", "Body parsed successfully", body_keys=list(body.keys()))
        
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON: {str(e)}"
        _log("WARN", error_msg, error=str(e), request_id=request_id)
        return _response(400, {"error": error_msg}, request_id=request_id)
    
    except Exception as e:
        error_msg = f"Unexpected error parsing body: {str(e)}"
        _log("ERROR", error_msg, error=str(e), traceback=traceback.format_exc(), request_id=request_id)
        return _response(500, {"error": "Internal server error"}, request_id=request_id)

    # ==================== FAZA 2: Validacija ====================
    
    if not isinstance(body, dict):
        error_msg = f"Body must be JSON object, got {type(body).__name__}"
        _log("WARN", error_msg, body_type=type(body).__name__, request_id=request_id)
        return _response(400, {"error": error_msg}, request_id=request_id)

    pk = body.get("PK")
    sk = body.get("SK")
    
    _log("DEBUG", "Validation check", pk=pk, sk=sk, request_id=request_id)
    
    if not pk or not sk:
        error_msg = "PK and SK are required"
        _log("WARN", error_msg, pk_present=bool(pk), sk_present=bool(sk), request_id=request_id)
        return _response(400, {"error": error_msg}, request_id=request_id)

    # ==================== FAZA 3: Upisivanje u bazu ====================
    
    try:
        _log("INFO", "Attempting to write item to DynamoDB",
             pk=pk, sk=sk, item_size=len(json.dumps(body)),
             request_id=request_id)
        
        table.put_item(Item=body)
        
        _log("INFO", "Item successfully written to DynamoDB",
             pk=pk, sk=sk, attributes_count=len(body),
             request_id=request_id)
        
        # ==================== FAZA 4: Uspešan odgovor ====================
        
        response_body = {"message": "Item created successfully", "item": body}
        _log("INFO", "POST /items completed successfully",
             status_code=201,
             pk=pk, sk=sk,
             response_size=len(json.dumps(response_body)),
             request_id=request_id)
        
        return _response(201, response_body, request_id=request_id)

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        
        _log("ERROR", f"DynamoDB ClientError: {error_code}",
             error_code=error_code,
             error_message=error_msg,
             pk=pk, sk=sk,
             request_id=request_id)
        
        # Mapiranje AWS grešaka na HTTP statuse
        if error_code == "ValidationException":
            return _response(400, {"error": f"Validation error: {error_msg}"}, request_id=request_id)
        elif error_code == "ProvisionedThroughputExceededException":
            return _response(429, {"error": "Too many requests, try again later"}, request_id=request_id)
        else:
            return _response(500, {"error": f"Database error: {error_code}"}, request_id=request_id)

    except Exception as e:
        _log("ERROR", "Unexpected error during item write",
             error=str(e),
             error_type=type(e).__name__,
             traceback=traceback.format_exc(),
             pk=pk, sk=sk,
             request_id=request_id)
        

        
        return _response(500, {"error": "Internal server error"}, request_id=request_id)