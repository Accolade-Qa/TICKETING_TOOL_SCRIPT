import asyncio
import aiohttp
import json
import os
import requests
from dotenv import load_dotenv

with open("payload.json", "r") as f:
    payloads = json.load(f)


load_dotenv()


def get_token():
    username = os.getenv("API_USERNAME")
    password = os.getenv("API_PASSWORD")

    response = requests.post(
        os.getenv("API_AUTH_URL"),
        json={"username": username, "password": password},
    )

    print(response.status_code)
    print(response.text)

    response.raise_for_status()

    token = response.json().get("token")
    print("TOKEN:", token)

    return token


token = get_token()
headers = {"Content-Type": "application/json", "token": f"{token}"}


async def send_request(session, payload):
    vin = payload["VIN_NO"]

    try:
        async with session.post(
            os.getenv("API_URL"), json=[payload], headers=headers
        ) as response:

            http_status = response.status

            try:
                response_json = await response.json(content_type=None)
            except Exception:
                response_text = await response.text()

                return {
                    "vin": vin,
                    "http_status": http_status,
                    "ticket_number": None,
                    "record_status": None,
                    "validation_errors": ["Non JSON Response"],
                    "response": response_text,
                }

            print("\n" + "=" * 100)
            print(f"VIN : {vin}")
            print(f"HTTP STATUS : {http_status}")
            print(json.dumps(response_json, indent=4))
            print("=" * 100)

            ticket_number = None
            record_status = None
            validation_errors = []

            data = response_json.get("data", [])

            if isinstance(data, list) and len(data) > 0:

                record = data[0]

                ticket_number = record.get("TICKET_NO")
                record_status = record.get("status")

                validation_errors = record.get("VALIDATION_ERROR", [])

            return {
                "vin": vin,
                "http_status": http_status,
                "ticket_number": ticket_number,
                "record_status": record_status,
                "validation_errors": validation_errors,
                "response": response_json,
            }

    except Exception as e:

        return {
            "vin": vin,
            "http_status": None,
            "ticket_number": None,
            "record_status": None,
            "validation_errors": [str(e)],
            "response": {},
        }


async def main():

    connector = aiohttp.TCPConnector(limit=10, ssl=False)

    timeout = aiohttp.ClientTimeout(total=60)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:

        tasks = []

        for payload in payloads:

            task = asyncio.create_task(send_request(session, payload))

            tasks.append(task)

            await asyncio.sleep(0.001)

        results = await asyncio.gather(*tasks, return_exceptions=True)

    print("\n\n")
    print("=" * 100)
    print("SUMMARY")
    print("=" * 100)

    tickets = []
    failed_vins = []
    duplicate_check = []

    for result in results:

        if isinstance(result, Exception):
            print(f"Task Exception : {result}")
            continue

        vin = result["vin"]
        ticket = result["ticket_number"]

        print(
            f"VIN={vin} | "
            f"HTTP={result['http_status']} | "
            f"TICKET={ticket} | "
            f"STATUS={result['record_status']}"
        )

        if ticket:
            tickets.append(ticket)
            duplicate_check.append(ticket)
        else:
            failed_vins.append(result)

    print("\n")
    print("=" * 100)
    print("FAILED REQUESTS")
    print("=" * 100)

    if failed_vins:

        for failure in failed_vins:

            print("\n")
            print(f"VIN : {failure['vin']}")
            print(f"HTTP : {failure['http_status']}")

            if failure["validation_errors"]:
                print("Errors:")

                for err in failure["validation_errors"]:
                    print(f" - {err}")

            print("Response:")

            try:
                print(json.dumps(failure["response"], indent=4))
            except:
                print(failure["response"])

    else:
        print("No failed requests.")

    print("\n")
    print("=" * 100)
    print("TICKET VALIDATION")
    print("=" * 100)

    print(f"Total Requests        : {len(results)}")

    print(f"Tickets Generated     : {len(tickets)}")

    print(f"Failed Requests       : {len(failed_vins)}")

    duplicates = len(duplicate_check) != len(set(duplicate_check))

    if duplicates:

        print("\nDUPLICATE TICKETS FOUND")

        seen = set()

        for ticket in duplicate_check:

            if ticket in seen:
                print(f"Duplicate Ticket : {ticket}")

            seen.add(ticket)

    else:
        print("\nPASS : All generated tickets are unique")

    print("\nGenerated Tickets:")

    for ticket in tickets:
        print(ticket)


if __name__ == "__main__":
    asyncio.run(main())
