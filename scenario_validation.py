import json
import os
from copy import deepcopy
import random

import requests
from dotenv import load_dotenv

load_dotenv()

PAYLOAD_FILE = "payload.json"
BASE_PAYLOAD = None

with open(PAYLOAD_FILE, "r") as f:
    loaded = json.load(f)
    if not loaded:
        raise RuntimeError("payload.json must contain at least one payload")
    BASE_PAYLOAD = loaded[0]


def get_token():
    username = os.getenv("API_USERNAME")
    password = os.getenv("API_PASSWORD")
    auth_url = os.getenv("API_AUTH_URL")

    if not username or not password or not auth_url:
        raise RuntimeError("API_USERNAME, API_PASSWORD, and API_AUTH_URL must be set")

    response = requests.post(
        auth_url, json={"username": username, "password": password}
    )
    response.raise_for_status()

    token = response.json().get("token")
    if not token:
        raise RuntimeError("Authentication response did not return a token")

    return token


def build_payload(modifications):
    payload = deepcopy(BASE_PAYLOAD)
    for key, value in modifications.items():
        payload[key] = value

    # Generate a random 4-digit suffix for VIN when not explicitly provided
    if not modifications.get("VIN_NO"):
        base_vin = payload.get("VIN_NO", "MAT0000")
        rand4 = f"{random.randint(0, 9999):04d}"
        if len(base_vin) >= 4 and base_vin[-4:].isdigit():
            payload["VIN_NO"] = base_vin[:-4] + rand4
        else:
            payload["VIN_NO"] = base_vin + rand4

    # Add default values for fields not present in the base payload
    payload.setdefault("VEHICLE_OWNER_EMAIL", "demo@gmail.com")
    payload.setdefault("VEHICLE_OWNER_ALTERNATE_MOBILE", "8787878787")

    return payload


def send_crm_request(payload_list, headers):
    api_url = os.getenv("API_URL")
    if not api_url:
        raise RuntimeError("API_URL must be set")

    response = requests.post(api_url, json=payload_list, headers=headers)
    result = {
        "http_status": response.status_code,
        "response_text": response.text,
        "response_json": None,
    }
    try:
        result["response_json"] = response.json()
    except ValueError:
        pass
    return result


def normalize_validation_errors(validation_errors):
    if validation_errors is None:
        return []
    if isinstance(validation_errors, str):
        return [validation_errors.strip()]
    if isinstance(validation_errors, list):
        return [str(err).strip() for err in validation_errors if err is not None]
    return [str(validation_errors).strip()]


def run_scenario(
    name,
    modifications,
    expected="unknown",
    expected_record_message=None,
    expected_validation_errors=None,
    expected_response_json=None,
    object_count=1,
):
    payload = build_payload(modifications)
    payload_list = [deepcopy(payload) for _ in range(object_count)]

    token = get_token()
    headers = {"Content-Type": "application/json", "token": token}

    result = send_crm_request(payload_list, headers)
    response_json = result.get("response_json") or {}

    scenario_result = {
        "name": name,
        "expected": expected,
        "payload": payload,
        "object_count": object_count,
        "http_status": result["http_status"],
        "response_json": response_json,
        "response_text": result["response_text"],
        "passed": False,
        "record_message": None,
        "record_status": None,
        "validation_errors": [],
        "expected_record_message": expected_record_message,
        "expected_validation_errors": normalize_validation_errors(
            expected_validation_errors
        ),
        "expected_response_json": expected_response_json,
    }

    if isinstance(response_json, dict):
        data = response_json.get("data")
        if isinstance(data, list) and data:
            record = data[0]
            scenario_result["record_message"] = (
                record.get("message") if record.get("message") is not None else None
            )
            scenario_result["record_status"] = record.get("status")
            scenario_result["validation_errors"] = normalize_validation_errors(
                record.get("VALIDATION_ERROR")
            )

    expected_message = expected_record_message or (
        "Data Saved Successfully!!" if expected == "accept" else None
    )

    response_json_ok = True
    if scenario_result["expected_response_json"] is not None:
        response_json_ok = (
            scenario_result["response_json"]
            == scenario_result["expected_response_json"]
        )

    if expected == "accept":
        record_message_ok = True
        if expected_message is not None:
            record_message_ok = scenario_result["record_message"] == expected_message

        validation_ok = True
        if scenario_result["expected_validation_errors"]:
            validation_ok = (
                scenario_result["validation_errors"]
                == scenario_result["expected_validation_errors"]
            )
        else:
            validation_ok = not scenario_result["validation_errors"]

        scenario_result["passed"] = (
            result["http_status"] in (200, 201)
            and record_message_ok
            and validation_ok
            and response_json_ok
        )
    elif expected == "reject":
        record_message_ok = True
        if expected_message is not None:
            record_message_ok = scenario_result["record_message"] == expected_message
        validation_ok = True
        if scenario_result["expected_validation_errors"]:
            validation_ok = (
                scenario_result["validation_errors"]
                == scenario_result["expected_validation_errors"]
            )
        else:
            validation_ok = bool(scenario_result["validation_errors"])

        scenario_result["passed"] = (
            (result["http_status"] >= 400 or bool(scenario_result["validation_errors"]))
            and record_message_ok
            and validation_ok
            and response_json_ok
        )
    else:
        scenario_result["passed"] = True

    return scenario_result


def print_result(result):
    print("\n" + "=" * 80)
    print(f"Scenario: {result['name']}")
    print(f"Expected: {result['expected']}")
    print(f"Object count: {result['object_count']}")
    print(f"HTTP status: {result['http_status']}")
    print(f"Passed: {result['passed']}")
    if result["validation_errors"]:
        print("Validation errors:")
        for err in result["validation_errors"]:
            print(f"  - {err}")
    if result["expected_record_message"] is not None:
        print(f"Expected record message: {result['expected_record_message']}")
    if result["expected_validation_errors"]:
        print("Expected validation errors:")
        for err in result["expected_validation_errors"]:
            print(f"  - {err}")
    if result["expected_response_json"] is not None:
        print("Expected response JSON:")
        print(json.dumps(result["expected_response_json"], indent=2))
    print("Response JSON:")
    if result["response_json"] is not None:
        print(json.dumps(result["response_json"], indent=2))
    else:
        print(result["response_text"])


def write_result_to_txt(result, filename="scenario_results.txt", append=True):
    mode = "a" if append else "w"
    with open(filename, mode, encoding="utf-8") as f:
        f.write(f"Scenario: {result['name']}\n")
        f.write(f"expected: {result['expected']}\n")
        f.write(f"object_count: {result['object_count']}\n")
        f.write(f"http_status: {result['http_status']}\n")
        f.write(f"passed: {result['passed']}\n")
        if result["record_message"] is not None:
            f.write(f"record_message: {result['record_message']}\n")
        if result["record_status"] is not None:
            f.write(f"record_status: {result['record_status']}\n")
        if result["validation_errors"]:
            f.write("validation_errors:\n")
            for err in result["validation_errors"]:
                f.write(f"  - {err}\n")
        if result["expected_record_message"] is not None:
            f.write(f"expected_record_message: {result['expected_record_message']}\n")
        if result["expected_validation_errors"]:
            f.write("expected_validation_errors:\n")
            for err in result["expected_validation_errors"]:
                f.write(f"  - {err}\n")
        if result["expected_response_json"] is not None:
            f.write("expected_response_json:\n")
            f.write(json.dumps(result["expected_response_json"], indent=2))
            f.write("\n")
        f.write("response_json:\n")
        if result["response_json"] is not None:
            f.write(json.dumps(result["response_json"], indent=2))
            f.write("\n")
        else:
            f.write(f"{result['response_text']}\n")
        f.write("" + "-" * 80 + "\n")


# Scenario functions
def test_vin_no_valid_format():
    return run_scenario(
        "VIN_NO valid format", {"VIN_NO": "MAT00003237212545"}, expected="accept"
    )


def test_vin_no_empty():
    return run_scenario("VIN_NO empty", {"VIN_NO": " "}, expected="reject")


def test_iccid_valid_format():
    return run_scenario(
        "ICCID valid format", {"ICCID": "89916420534724851291"}, expected="accept"
    )


def test_iccid_empty():
    return run_scenario("ICCID empty", {"ICCID": " "}, expected="reject")


def test_iccid_not_in_database():
    return run_scenario(
        "ICCID not present in database",
        {"ICCID": "89916490634626390749"},
        expected="reject",
    )


def test_engine_no_valid_format():
    return run_scenario(
        "ENGINE_NO valid format", {"ENGINE_NO": "VARICOR11BYXJ03874"}, expected="accept"
    )


def test_engine_no_empty():
    return run_scenario("ENGINE_NO empty", {"ENGINE_NO": " "}, expected="reject")


def test_reg_number_valid_format():
    return run_scenario(
        "REG_NUMBER valid format", {"REG_NUMBER": "PB09AZ2103"}, expected="accept"
    )


def test_reg_number_empty():
    return run_scenario("REG_NUMBER empty", {"REG_NUMBER": ""}, expected="reject")


def test_vehicle_model_valid_format():
    return run_scenario(
        "VEHICLE_MODEL valid format", {"VEHICLE_MODEL": "TATA Ace"}, expected="accept"
    )


def test_vehicle_model_empty():
    return run_scenario(
        "VEHICLE_MODEL empty", {"VEHICLE_MODEL": " "}, expected="reject"
    )


def test_mfg_year_valid_format():
    return run_scenario(
        "MFG_YEAR valid format", {"MFG_YEAR": "2023"}, expected="accept"
    )


def test_mfg_year_empty():
    return run_scenario("MFG_YEAR empty", {"MFG_YEAR": ""}, expected="reject")


def test_invoice_number_valid_format():
    return run_scenario(
        "INVOICE_NUMBER valid format", {"INVOICE_NUMBER": "2023"}, expected="accept"
    )


def test_invoice_number_empty():
    return run_scenario(
        "INVOICE_NUMBER empty", {"INVOICE_NUMBER": ""}, expected="reject"
    )


def test_invoice_date_valid_format():
    return run_scenario(
        "INVOICE_DATE valid format", {"INVOICE_DATE": "11/10/2023"}, expected="accept"
    )


def test_invoice_date_empty():
    return run_scenario("INVOICE_DATE empty", {"INVOICE_DATE": ""}, expected="reject")


def test_uin_no_valid_format():
    return run_scenario(
        "UIN_NO valid format", {"UIN_NO": "ACON4NA202200082103"}, expected="accept"
    )


def test_uin_no_empty():
    return run_scenario("UIN_NO empty", {"UIN_NO": ""}, expected="reject")


def test_uin_no_alphanumeric_invalid():
    return run_scenario(
        "UIN_NO alphanumeric invalid",
        {"UIN_NO": "ACON4NA082300092233dasdw"},
        expected="reject",
    )


def test_device_imei_valid_format():
    return run_scenario(
        "DEVICE_IMEI valid format",
        {"DEVICE_IMEI": "868274067382103"},
        expected="accept",
    )


def test_device_imei_empty():
    return run_scenario("DEVICE_IMEI empty", {"DEVICE_IMEI": ""}, expected="reject")


def test_device_imei_alphanumeric_invalid():
    return run_scenario(
        "DEVICE_IMEI alphanumeric invalid",
        {"DEVICE_IMEI": "861564061380138sd"},
        expected="reject",
    )


def test_device_make_valid_format():
    return run_scenario(
        "DEVICE_MAKE valid format", {"DEVICE_MAKE": "ACCOLADE"}, expected="accept"
    )


def test_device_make_empty():
    return run_scenario("DEVICE_MAKE empty", {"DEVICE_MAKE": ""}, expected="reject")


def test_device_make_non_accolade():
    return run_scenario(
        "DEVICE_MAKE non-accolade", {"DEVICE_MAKE": "Google"}, expected="reject"
    )


def test_device_model_valid_format():
    return run_scenario(
        "DEVICE_MODEL valid format", {"DEVICE_MODEL": "AEPL051401"}, expected="accept"
    )


def test_device_model_empty():
    return run_scenario("DEVICE_MODEL empty", {"DEVICE_MODEL": ""}, expected="reject")


def test_device_model_incorrect():
    return run_scenario(
        "DEVICE_MODEL incorrect", {"DEVICE_MODEL": "ACON6PA"}, expected="reject"
    )


def test_primary_operator_valid_format():
    return run_scenario(
        "PRIMARY_OPERATOR valid format", {"PRIMARY_OPERATOR": "BSNL"}, expected="accept"
    )


def test_primary_operator_empty():
    return run_scenario(
        "PRIMARY_OPERATOR empty", {"PRIMARY_OPERATOR": ""}, expected="reject"
    )


def test_primary_mobile_number_valid_format():
    return run_scenario(
        "PRIMARY_MOBILE_NUMBER valid format",
        {"PRIMARY_MOBILE_NUMBER": "123456789012345"},
        expected="accept",
    )


def test_primary_mobile_number_empty():
    return run_scenario(
        "PRIMARY_MOBILE_NUMBER empty", {"PRIMARY_MOBILE_NUMBER": ""}, expected="reject"
    )


def test_primary_mobile_number_non_digit():
    return run_scenario(
        "PRIMARY_MOBILE_NUMBER not digit",
        {"PRIMARY_MOBILE_NUMBER": "9898989898abcde"},
        expected="reject",
    )


def test_primary_mobile_number_too_long():
    return run_scenario(
        "PRIMARY_MOBILE_NUMBER too long",
        {"PRIMARY_MOBILE_NUMBER": "9157542035598721"},
        expected="reject",
    )


def test_secondary_operator_valid_format():
    return run_scenario(
        "SECONDARY_OPERATOR valid format",
        {"SECONDARY_OPERATOR": "BHA"},
        expected="accept",
    )


def test_secondary_operator_empty():
    return run_scenario(
        "SECONDARY_OPERATOR empty", {"SECONDARY_OPERATOR": ""}, expected="reject"
    )


def test_secondary_mobile_number_valid_format():
    return run_scenario(
        "SECONDARY_MOBILE_NUMBER valid format",
        {"SECONDARY_MOBILE_NUMBER": "989856789012345"},
        expected="accept",
    )


def test_secondary_mobile_number_empty():
    return run_scenario(
        "SECONDARY_MOBILE_NUMBER empty",
        {"SECONDARY_MOBILE_NUMBER": ""},
        expected="reject",
    )


def test_secondary_mobile_number_non_digit():
    return run_scenario(
        "SECONDARY_MOBILE_NUMBER not digit",
        {"SECONDARY_MOBILE_NUMBER": "abcdefghijklm"},
        expected="reject",
    )


def test_secondary_mobile_number_too_long():
    return run_scenario(
        "SECONDARY_MOBILE_NUMBER too long",
        {"SECONDARY_MOBILE_NUMBER": "9157542035598721"},
        expected="reject",
    )


def test_commercial_activation_start_date_valid_format():
    return run_scenario(
        "COMMERCIAL_ACTIVATION_START_DATE valid format",
        {"COMMERCIAL_ACTIVATION_START_DATE": "11/10/2023"},
        expected="accept",
    )


def test_commercial_activation_start_date_empty():
    return run_scenario(
        "COMMERCIAL_ACTIVATION_START_DATE empty",
        {"COMMERCIAL_ACTIVATION_START_DATE": " "},
        expected="reject",
    )


def test_commercial_activation_expiry_date_valid_format():
    return run_scenario(
        "COMMERCIAL_ACTIVATION_EXPIRY_DATE valid format",
        {"COMMERCIAL_ACTIVATION_EXPIRY_DATE": "11/10/2025"},
        expected="accept",
    )


def test_commercial_activation_expiry_date_empty():
    return run_scenario(
        "COMMERCIAL_ACTIVATION_EXPIRY_DATE empty",
        {"COMMERCIAL_ACTIVATION_EXPIRY_DATE": ""},
        expected="reject",
    )


def test_commercial_activation_expiry_date_two_years_ahead():
    return run_scenario(
        "COMMERCIAL_ACTIVATION_EXPIRY_DATE two years ahead",
        {"COMMERCIAL_ACTIVATION_EXPIRY_DATE": "2028-07-07"},
        expected="accept",
    )


def test_vehicle_owner_first_name_valid_format():
    return run_scenario(
        "VEHICLE_OWNER_FIRST_NAME valid format",
        {"VEHICLE_OWNER_FIRST_NAME": "Shital"},
        expected="accept",
    )


def test_vehicle_owner_middle_name_valid_format():
    return run_scenario(
        "VEHICLE_OWNER_MIDDLE_NAME valid format",
        {"VEHICLE_OWNER_MIDDLE_NAME": "XYZ"},
        expected="accept",
    )


def test_vehicle_owner_last_name_valid_format():
    return run_scenario(
        "VEHICLE_OWNER_LAST_NAME valid format",
        {"VEHICLE_OWNER_LAST_NAME": "ABC"},
        expected="accept",
    )


def test_vehicle_owner_last_name_empty():
    return run_scenario(
        "VEHICLE_OWNER_LAST_NAME empty",
        {"VEHICLE_OWNER_LAST_NAME": ""},
        expected="reject",
    )


def test_vehicle_owner_address_line_1_valid_format():
    return run_scenario(
        "VEHICLE_OWNER_ADDRESS_LINE_1 valid format",
        {"VEHICLE_OWNER_ADDRESS_LINE_1": "ABC"},
        expected="accept",
    )


def test_vehicle_owner_address_line_1_empty():
    return run_scenario(
        "VEHICLE_OWNER_ADDRESS_LINE_1 empty",
        {"VEHICLE_OWNER_ADDRESS_LINE_1": ""},
        expected="reject",
    )


def test_vehicle_owner_address_line_2_valid_format():
    return run_scenario(
        "VEHICLE_OWNER_ADDRESS_LINE_2 valid format",
        {"VEHICLE_OWNER_ADDRESS_LINE_2": "ABC"},
        expected="accept",
    )


def test_vehicle_owner_city_valid_format():
    return run_scenario(
        "VEHICLE_OWNER_CITY valid format",
        {"VEHICLE_OWNER_CITY": "ABC"},
        expected="accept",
    )


def test_vehicle_owner_city_empty():
    return run_scenario(
        "VEHICLE_OWNER_CITY empty", {"VEHICLE_OWNER_CITY": ""}, expected="reject"
    )


def test_vehicle_owner_district_valid_format():
    return run_scenario(
        "VEHICLE_OWNER_DISTRICT valid format",
        {"VEHICLE_OWNER_DISTRICT": "ABC"},
        expected="accept",
    )


def test_vehicle_owner_state_valid_format():
    return run_scenario(
        "VEHICLE_OWNER_STATE valid format",
        {"VEHICLE_OWNER_STATE": "ABC"},
        expected="accept",
    )


def test_vehicle_owner_country_valid_format():
    return run_scenario(
        "VEHICLE_OWNER_COUNTRY valid format",
        {"VEHICLE_OWNER_COUNTRY": "ABC"},
        expected="accept",
    )


def test_vehicle_owner_pincode_valid_format():
    return run_scenario(
        "VEHICLE_OWNER_PINCODE valid format",
        {"VEHICLE_OWNER_PINCODE": "411045"},
        expected="accept",
    )


def test_vehicle_owner_registered_mobile_valid_format():
    return run_scenario(
        "VEHICLE_OWNER_REGISTERED_MOBILE valid format",
        {"VEHICLE_OWNER_REGISTERED_MOBILE": "1234567890"},
        expected="accept",
    )


def test_vehicle_owner_registered_mobile_empty():
    return run_scenario(
        "VEHICLE_OWNER_REGISTERED_MOBILE empty",
        {"VEHICLE_OWNER_REGISTERED_MOBILE": ""},
        expected="reject",
    )


def test_vehicle_owner_registered_mobile_too_long():
    return run_scenario(
        "VEHICLE_OWNER_REGISTERED_MOBILE too long",
        {"VEHICLE_OWNER_REGISTERED_MOBILE": "12345678901"},
        expected="reject",
    )


def test_vehicle_owner_registered_mobile_non_digit():
    return run_scenario(
        "VEHICLE_OWNER_REGISTERED_MOBILE non-digit",
        {"VEHICLE_OWNER_REGISTERED_MOBILE": "abcdefghij"},
        expected="reject",
    )


def test_vehicle_owner_alternate_mobile_valid_format():
    return run_scenario(
        "VEHICLE_OWNER_ALTERNATE_MOBILE valid format",
        {"VEHICLE_OWNER_ALTERNATE_MOBILE": "1234567890"},
        expected="accept",
    )


def test_vehicle_owner_alternate_mobile_empty():
    return run_scenario(
        "VEHICLE_OWNER_ALTERNATE_MOBILE empty",
        {"VEHICLE_OWNER_ALTERNATE_MOBILE": ""},
        expected="reject",
    )


def test_vehicle_owner_alternate_mobile_too_long():
    return run_scenario(
        "VEHICLE_OWNER_ALTERNATE_MOBILE too long",
        {"VEHICLE_OWNER_ALTERNATE_MOBILE": "12345678901"},
        expected="reject",
    )


def test_vehicle_owner_alternate_mobile_non_digit():
    return run_scenario(
        "VEHICLE_OWNER_ALTERNATE_MOBILE non-digit",
        {"VEHICLE_OWNER_ALTERNATE_MOBILE": "abcdefghij"},
        expected="reject",
    )


def test_vehicle_owner_email_valid_format():
    return run_scenario(
        "VEHICLE_OWNER_EMAIL valid format",
        {"VEHICLE_OWNER_EMAIL": "demo@gmail.com"},
        expected="accept",
    )


def test_vehicle_owner_email_invalid_format():
    return run_scenario(
        "VEHICLE_OWNER_EMAIL invalid format",
        {"VEHICLE_OWNER_EMAIL": "demogmail.com"},
        expected="reject",
    )


def test_vehicle_owner_email_empty():
    return run_scenario(
        "VEHICLE_OWNER_EMAIL empty",
        {"VEHICLE_OWNER_EMAIL": ""},
        expected="reject",
    )


def test_dealer_code_valid_format():
    return run_scenario(
        "DEALER_CODE valid format", {"DEALER_CODE": "100B710"}, expected="accept"
    )


def test_dealer_code_empty():
    return run_scenario("DEALER_CODE empty", {"DEALER_CODE": ""}, expected="reject")


def test_pos_code_valid_format():
    return run_scenario(
        "POS_CODE valid format", {"POS_CODE": "100B710"}, expected="accept"
    )


def test_poa_doc_name_valid_format():
    return run_scenario(
        "POA_DOC_NAME valid format", {"POA_DOC_NAME": "Adhar"}, expected="accept"
    )


def test_poa_doc_name_empty():
    return run_scenario("POA_DOC_NAME empty", {"POA_DOC_NAME": ""}, expected="reject")


def test_poa_doc_no_valid_format():
    return run_scenario(
        "POA_DOC_NO valid format", {"POA_DOC_NO": "123456789012"}, expected="accept"
    )


def test_poa_doc_no_empty():
    return run_scenario("POA_DOC_NO empty", {"POA_DOC_NO": ""}, expected="reject")


def test_poi_doc_type_valid_format():
    return run_scenario(
        "POI_DOC_TYPE valid format", {"POI_DOC_TYPE": "PAN"}, expected="accept"
    )


def test_poi_doc_type_empty():
    return run_scenario("POI_DOC_TYPE empty", {"POI_DOC_TYPE": ""}, expected="reject")


def test_poi_doc_no_valid_format():
    return run_scenario(
        "POI_DOC_NO valid format", {"POI_DOC_NO": "ABCD123E"}, expected="accept"
    )


def test_poi_doc_no_empty():
    return run_scenario("POI_DOC_NO empty", {"POI_DOC_NO": ""}, expected="reject")


def test_rto_state_valid_format():
    return run_scenario(
        "RTO_STATE valid format", {"RTO_STATE": "MH"}, expected="accept"
    )


def test_rto_state_empty():
    return run_scenario("RTO_STATE empty", {"RTO_STATE": ""}, expected="reject")


def test_rto_office_code_valid_format():
    return run_scenario(
        "RTO_OFFICE_CODE valid format", {"RTO_OFFICE_CODE": "MH 09"}, expected="accept"
    )


def test_rto_office_code_empty():
    return run_scenario(
        "RTO_OFFICE_CODE empty", {"RTO_OFFICE_CODE": ""}, expected="reject"
    )


def test_certificate_validity_duration_in_year_valid_format():
    return run_scenario(
        "CERTIFICATE_VALIDITY_DURATION_IN_YEAR valid format",
        {"CERTIFICATE_VALIDITY_DURATION_IN_YEAR": "2"},
        expected="accept",
    )


def test_certificate_validity_duration_in_year_empty():
    return run_scenario(
        "CERTIFICATE_VALIDITY_DURATION_IN_YEAR empty",
        {"CERTIFICATE_VALIDITY_DURATION_IN_YEAR": ""},
        expected="reject",
    )


def test_same_objects_two_requests():
    return run_scenario(
        "ALL PARAMETERS ARE THE SAME for 2 objects",
        {},
        expected="unknown",
        object_count=2,
    )


def test_change_request_after_stage_2():

    # need to add the api call to complete stage 2 before running this scenario, otherwise it will fail
    return run_scenario(
        "CHANGE REQUEST AFTER STAGE 2",
        {"RTO_OFFICE_CODE": "MZ 11", "RTO_STATE": "MZ"},
        expected="unknown",
    )


def test_ticket_cancelled_device_change():
    return run_scenario(
        "Ticket Cancelled Due to Change Request Device Change",
        {
            "ICCID": "12345678901234567890",
            "UIN_NO": "ACON4NA102300012345",
            "DEVICE_IMEI": "123456789012345",
            "PRIMARY_OPERATOR": "BSNL",
            "PRIMARY_MOBILE_NUMBER": "123456789012345",
            "SECONDARY_OPERATOR": "BHA",
            "SECONDARY_MOBILE_NUMBER": "123456789012345",
            "OVERALL_REMARK": "Ticket Cancelled Due to Change Request Device Change",
        },
        expected="unknown",
    )


def test_ticket_cancelled_vehicle_owner_change():
    return run_scenario(
        "Ticket Cancelled Due to Change Request Vehicle Owner Change",
        {
            "VEHICLE_OWNER_FIRST_NAME": "ABC",
            "VEHICLE_OWNER_LAST_NAME": "abc",
            "VEHICLE_OWNER_ADDRESS_LINE_1": "ABC",
            "VEHICLE_OWNER_CITY": "ABC",
            "VEHICLE_OWNER_REGISTERED_MOBILE": "1234567890",
            "POA_DOC_NAME": "ADHAR",
            "POA_DOC_NO": "123456789012",
            "POI_DOC_TYPE": "PAN",
            "POI_DOC_NO": "PAN123AB",
            "OVERALL_REMARK": "Ticket Cancelled Due to Change Request Vehicle Owner Change",
        },
        expected="unknown",
    )


def test_ticket_cancelled_rto_state_change():
    return run_scenario(
        "Ticket Cancelled Due to Change Request RTO or State Change",
        {
            "RTO_OFFICE_CODE": "MZ 11",
            "RTO_STATE": "MZ",
            "OVERALL_REMARK": "Ticket Cancelled Due to Change Request RTO or State Change",
        },
        expected="unknown",
    )


def test_ticket_cancelled_as_per_request():
    return run_scenario(
        "Ticket Cancelled as per Request",
        {"OVERALL_REMARK": "Ticket Cancelled as per Request"},
        expected="unknown",
    )


def test_ticket_cancelled_due_to_invoice_cancelled():
    return run_scenario(
        "Ticket Cancelled Due to Invoice Cancelled",
        {"OVERALL_REMARK": "Ticket Cancelled Due to Invoice Cancelled"},
        expected="unknown",
    )


def test_change_required_from_crm():
    return run_scenario(
        "Change required from CRM",
        {"OVERALL_REMARK": "Change required from CRM"},
        expected="unknown",
    )


def test_other_overall_remark_option():
    return run_scenario(
        "Other overall remark option",
        {"OVERALL_REMARK": "Other"},
        expected="unknown",
    )


def test_on_hold_non_working_hours():
    return run_scenario(
        "On Hold Due to Non-Working Hours",
        {"OVERALL_REMARK": "On Hold Due to Non-Working Hours"},
        expected="unknown",
    )


def test_on_hold_sim_validity_issue():
    return run_scenario(
        "On Hold Due to SIM Validity Issue",
        {"OVERALL_REMARK": "On Hold Due to SIM Validity Issue"},
        expected="unknown",
    )


def test_ticket_suspended_customer_not_responding():
    return run_scenario(
        "Ticket Suspended Due to Customer Not Responding",
        {"OVERALL_REMARK": "Ticket Suspended Due to Customer Not Responding"},
        expected="unknown",
    )


def test_institutional_sales_ticket():
    return run_scenario(
        "Institutional sales ticket payload",
        {"INSTITUTIONAL_SALES": "YES", "OVERALL_REMARK": "Institutional sales ticket"},
        expected="unknown",
    )


def test_crm_request_with_multiple_objects():
    return run_scenario(
        "CRM request with multiple objects",
        {},
        expected="unknown",
        object_count=2,
    )


SCENARIO_FUNCTIONS = [
    test_vin_no_valid_format,
    test_vin_no_empty,
    test_iccid_valid_format,
    test_iccid_empty,
    test_iccid_not_in_database,
    test_engine_no_valid_format,
    test_engine_no_empty,
    test_reg_number_valid_format,
    test_reg_number_empty,
    test_vehicle_model_valid_format,
    test_vehicle_model_empty,
    test_mfg_year_valid_format,
    test_mfg_year_empty,
    test_invoice_number_valid_format,
    test_invoice_number_empty,
    test_invoice_date_valid_format,
    test_invoice_date_empty,
    test_uin_no_valid_format,
    test_uin_no_empty,
    test_uin_no_alphanumeric_invalid,
    test_device_imei_valid_format,
    test_device_imei_empty,
    test_device_imei_alphanumeric_invalid,
    test_device_make_valid_format,
    test_device_make_empty,
    test_device_make_non_accolade,
    test_device_model_valid_format,
    test_device_model_empty,
    test_device_model_incorrect,
    test_primary_operator_valid_format,
    test_primary_operator_empty,
    test_primary_mobile_number_valid_format,
    test_primary_mobile_number_empty,
    test_primary_mobile_number_non_digit,
    test_primary_mobile_number_too_long,
    test_secondary_operator_valid_format,
    test_secondary_operator_empty,
    test_secondary_mobile_number_valid_format,
    test_secondary_mobile_number_empty,
    test_secondary_mobile_number_non_digit,
    test_secondary_mobile_number_too_long,
    test_commercial_activation_start_date_valid_format,
    test_commercial_activation_start_date_empty,
    test_commercial_activation_expiry_date_valid_format,
    test_commercial_activation_expiry_date_empty,
    test_commercial_activation_expiry_date_two_years_ahead,
    test_vehicle_owner_first_name_valid_format,
    test_vehicle_owner_middle_name_valid_format,
    test_vehicle_owner_last_name_valid_format,
    test_vehicle_owner_last_name_empty,
    test_vehicle_owner_address_line_1_valid_format,
    test_vehicle_owner_address_line_1_empty,
    test_vehicle_owner_address_line_2_valid_format,
    test_vehicle_owner_city_valid_format,
    test_vehicle_owner_city_empty,
    test_vehicle_owner_district_valid_format,
    test_vehicle_owner_state_valid_format,
    test_vehicle_owner_country_valid_format,
    test_vehicle_owner_pincode_valid_format,
    test_vehicle_owner_registered_mobile_valid_format,
    test_vehicle_owner_registered_mobile_empty,
    test_vehicle_owner_registered_mobile_too_long,
    test_vehicle_owner_registered_mobile_non_digit,
    test_vehicle_owner_alternate_mobile_valid_format,
    test_vehicle_owner_alternate_mobile_empty,
    test_vehicle_owner_alternate_mobile_too_long,
    test_vehicle_owner_alternate_mobile_non_digit,
    test_vehicle_owner_email_valid_format,
    test_vehicle_owner_email_invalid_format,
    test_vehicle_owner_email_empty,
    test_dealer_code_valid_format,
    test_dealer_code_empty,
    test_pos_code_valid_format,
    test_poa_doc_name_valid_format,
    test_poa_doc_name_empty,
    test_poa_doc_no_valid_format,
    test_poa_doc_no_empty,
    test_poi_doc_type_valid_format,
    test_poi_doc_type_empty,
    test_poi_doc_no_valid_format,
    test_poi_doc_no_empty,
    test_rto_state_valid_format,
    test_rto_state_empty,
    test_rto_office_code_valid_format,
    test_rto_office_code_empty,
    test_certificate_validity_duration_in_year_valid_format,
    test_certificate_validity_duration_in_year_empty,
    test_same_objects_two_requests,
    test_change_request_after_stage_2,
    test_ticket_cancelled_device_change,
    test_ticket_cancelled_vehicle_owner_change,
    test_ticket_cancelled_rto_state_change,
    test_ticket_cancelled_as_per_request,
    test_ticket_cancelled_due_to_invoice_cancelled,
    test_change_required_from_crm,
    test_other_overall_remark_option,
    test_on_hold_non_working_hours,
    test_on_hold_sim_validity_issue,
    test_ticket_suspended_customer_not_responding,
    test_institutional_sales_ticket,
    test_crm_request_with_multiple_objects,
]


def main():
    print("Starting scenario validation run...")
    passed = 0
    failed = 0

    output_file = "scenario_results.txt"
    if os.path.exists(output_file):
        os.remove(output_file)

    for scenario_fn in SCENARIO_FUNCTIONS:
        print("\n" + "-" * 80)
        result = scenario_fn()
        print_result(result)
        write_result_to_txt(result, filename=output_file, append=True)
        if result["passed"]:
            passed += 1
        else:
            failed += 1

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total scenarios: {len(SCENARIO_FUNCTIONS)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")


if __name__ == "__main__":
    main()
