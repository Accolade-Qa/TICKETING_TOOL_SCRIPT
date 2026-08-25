import json
import random
from copy import deepcopy
from pathlib import Path


def load_base_payload(payload_file=None):
    path = Path(payload_file) if payload_file else (
        Path(__file__).resolve().parents[1] / "data" / "payload.json"
    )
    with path.open(encoding="utf-8") as payload_handle:
        loaded = json.load(payload_handle)
    if not loaded:
        raise RuntimeError("payload.json must contain at least one payload")
    return loaded[0]


def build_payload(base_payload, modifications):
    payload = deepcopy(base_payload)
    payload.update(modifications)
    if not modifications.get("VIN_NO"):
        base_vin = payload.get("VIN_NO", "MAT0000")
        rand4 = f"{random.randint(0, 9999):04d}"
        if len(base_vin) >= 4 and base_vin[-4:].isdigit():
            payload["VIN_NO"] = base_vin[:-4] + rand4
        else:
            payload["VIN_NO"] = base_vin + rand4
    payload.setdefault("VEHICLE_OWNER_EMAIL", "demo@gmail.com")
    payload.setdefault("VEHICLE_OWNER_ALTERNATE_MOBILE", "8787878787")
    return payload
