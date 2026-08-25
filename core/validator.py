def normalize_errors(errors):
    if errors is None:
        return []
    if isinstance(errors, str):
        return [errors.strip()]
    if isinstance(errors, list):
        return [str(error).strip() for error in errors if error is not None]
    return [str(errors).strip()]


def validate_response(api_result, expected="unknown", expected_record_message=None,
                      expected_validation_errors=None, expected_response_json=None):
    response_json = api_result.get("response_json") or {}
    record = {}
    data = response_json.get("data") if isinstance(response_json, dict) else None
    if isinstance(data, list) and data:
        record = data[0] if isinstance(data[0], dict) else {}
    errors = normalize_errors(record.get("VALIDATION_ERROR"))
    expected_errors = normalize_errors(expected_validation_errors)
    actual_message = record.get("message")
    expected_message = expected_record_message or (
        "Data Saved Successfully!!" if expected == "accept" else None
    )
    message_ok = expected_message is None or actual_message == expected_message
    response_json_ok = expected_response_json is None or response_json == expected_response_json
    if expected == "accept":
        validation_ok = errors == expected_errors if expected_errors else not errors
        passed = api_result["http_status"] in (200, 201) and message_ok and validation_ok and response_json_ok
    elif expected == "reject":
        validation_ok = errors == expected_errors if expected_errors else bool(errors)
        passed = (api_result["http_status"] >= 400 or bool(errors)) and message_ok and validation_ok and response_json_ok
    else:
        passed = True
    return {
        "response_json": response_json,
        "record_message": actual_message,
        "record_status": record.get("status"),
        "ticket_number": record.get("TICKET_NO"),
        "validation_errors": errors,
        "expected_validation_errors": expected_errors,
        "passed": passed,
    }
