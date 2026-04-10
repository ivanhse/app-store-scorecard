import json
import time
import requests
import jwt


TOKEN_URL = "https://appleid.apple.com/auth/oauth2/token"
ADS_API_BASE = "https://api.searchads.apple.com/api/v5"


class SearchAdsClient:
    """Apple Search Ads API client for keyword popularity data."""

    def __init__(self, client_id, team_id, key_id, private_key_path):
        self.client_id = client_id
        self.team_id = team_id
        self.key_id = key_id
        with open(private_key_path, "r") as f:
            self.private_key = f.read()
        self._access_token = None
        self._token_expires = 0

    def _generate_client_secret(self):
        now = int(time.time())
        payload = {
            "sub": self.client_id,
            "aud": "https://appleid.apple.com",
            "iat": now,
            "exp": now + 3600,
            "iss": self.team_id,
        }
        headers = {
            "kid": self.key_id,
            "alg": "ES256",
        }
        return jwt.encode(payload, self.private_key, algorithm="ES256", headers=headers)

    def _get_access_token(self):
        if self._access_token and time.time() < self._token_expires:
            return self._access_token

        client_secret = self._generate_client_secret()
        resp = requests.post(TOKEN_URL, data={
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": client_secret,
            "scope": "searchadsorg",
        }, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access_token"]
        self._token_expires = time.time() + data.get("expires_in", 3600) - 60
        return self._access_token

    def _headers(self):
        return {
            "Authorization": f"Bearer {self._get_access_token()}",
            "X-AP-Context": f"orgId={self.team_id}",
            "Content-Type": "application/json",
        }

    def get_keyword_recommendations(self, app_id, country="US"):
        """Get keyword suggestions + popularity scores for an app."""
        url = f"{ADS_API_BASE}/keywords/targeting"
        body = {
            "appId": str(app_id),
            "countryOrRegion": country,
        }
        resp = requests.post(url, headers=self._headers(), json=body, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        keywords = []
        for kw in data.get("data", []):
            attrs = kw.get("attributes", kw)
            keywords.append({
                "keyword": attrs.get("text", ""),
                "popularity": attrs.get("searchPopularity", 0),
                "match_type": attrs.get("matchType", ""),
            })

        return sorted(keywords, key=lambda k: k["popularity"], reverse=True)


def load_client_from_env():
    """Load Search Ads client from .env file or environment variables."""
    import os
    from pathlib import Path

    # Try .env file in project root
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())

    client_id = os.environ.get("APPLE_ADS_CLIENT_ID")
    team_id = os.environ.get("APPLE_ADS_TEAM_ID")
    key_id = os.environ.get("APPLE_ADS_KEY_ID")
    key_path = os.environ.get("APPLE_ADS_PRIVATE_KEY_PATH")

    if not all([client_id, team_id, key_id, key_path]):
        return None

    return SearchAdsClient(client_id, team_id, key_id, key_path)
