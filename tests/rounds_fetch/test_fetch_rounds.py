import json
from html import unescape
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.canada.ca"
ROUNDS_PAGE = (
    "/en/immigration-refugees-citizenship/"
    "services/immigrate-canada/express-entry/rounds-invitations.html"
)


def fetch_rounds_json_url():
    """Locate the latest rounds JSON endpoint from the public IRCC page."""
    response = requests.get(urljoin(BASE_URL, ROUNDS_PAGE), timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    data_cfg = None
    for element in soup.select("[data-wb-json]"):
        try:
            config = json.loads(unescape(element["data-wb-json"]))
        except json.JSONDecodeError:
            continue
        url = config.get("url", "")
        if "ee_rounds" in url:
            data_cfg = config
            break

    if not data_cfg or "url" not in data_cfg:
        raise RuntimeError("Could not locate rounds JSON configuration on IRCC page.")

    json_path = data_cfg["url"].split("#", 1)[0]
    return urljoin(BASE_URL, json_path)


def fetch_rounds():
    """Download the latest rounds payload."""
    json_url = fetch_rounds_json_url()
    response = requests.get(json_url, timeout=30)
    response.raise_for_status()
    payload = response.json()
    rounds = payload.get("rounds", [])
    if not rounds:
        raise RuntimeError("No rounds found in payload.")
    return json_url, rounds


def main():
    json_url, rounds = fetch_rounds()
    latest = rounds[0]
    print(f"Rounds JSON endpoint: {json_url}")
    print(f"Total rounds retrieved: {len(rounds)}")
    print("Most recent draw:")
    print(
        f"  #{latest.get('drawNumber')} | "
        f"{latest.get('drawDateFull')} | "
        f"{latest.get('drawName')} | "
        f"Invitations: {latest.get('drawSize')} | "
        f"Cut-off: {latest.get('drawCRS')}"
    )


if __name__ == "__main__":
    main()
