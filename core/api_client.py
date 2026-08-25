import os
import time

import requests
from dotenv import load_dotenv


class ApiClient:
    def __init__(self, timeout=60):
        load_dotenv()
        self.timeout = timeout
        self.token = None

    def authenticate(self):
        username = os.getenv("API_USERNAME")
        password = os.getenv("API_PASSWORD")
        auth_url = os.getenv("API_AUTH_URL")
        if not username or not password or not auth_url:
            raise RuntimeError("API_USERNAME, API_PASSWORD, and API_AUTH_URL must be set")
        response = requests.post(
            auth_url,
            json={"username": username, "password": password},
            timeout=self.timeout,
        )
        response.raise_for_status()
        self.token = response.json().get("token")
        if not self.token:
            raise RuntimeError("Authentication response did not return a token")
        return self.token

    def send(self, payload_list):
        api_url = os.getenv("API_URL")
        if not api_url:
            raise RuntimeError("API_URL must be set")
        if not self.token:
            self.authenticate()
        started = time.perf_counter()
        response = requests.post(
            api_url,
            json=payload_list,
            headers={"Content-Type": "application/json", "token": self.token},
            timeout=self.timeout,
        )
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        try:
            response_json = response.json()
        except ValueError:
            response_json = None
        return {
            "http_status": response.status_code,
            "response_text": response.text,
            "response_json": response_json,
            "duration_ms": duration_ms,
        }
