"""Authenticated StockTerminal account API. Never persist plaintext bearer tokens."""
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

class CloudError(RuntimeError):
    pass

class Cloud:
    def __init__(self, session):
        self.session = session
        self.base = session.get("api_base", "http://127.0.0.1:8000").rstrip("/")
        self.token = session.get("token") or session.get("access_token")
        if not self.token:
            raise CloudError("Account session has no decrypted access token")

    def request(self, method, path, payload=None):
        data = None if payload is None else json.dumps(payload, allow_nan=False).encode("utf-8")
        request = Request(self.base + path, data=data, method=method,
            headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=8) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            try:
                detail = json.loads(exc.read().decode("utf-8")).get("detail", "Request failed")
            except Exception:
                detail = "Request failed"
            raise CloudError(f"Server returned {exc.code}: {detail}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise CloudError(f"Account server unavailable: {exc}") from exc
