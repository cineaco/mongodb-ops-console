from typing import Any, Generator, Optional
import httpx

from app.cli import config, formatters


class APIClient:
    def __init__(self, override_url: Optional[str] = None):
        cfg = config.load_config()
        self.base_url = (override_url or cfg.get("api_url") or config.DEFAULT_API_URL).rstrip("/")
        self.access_token = cfg.get("access_token")
        self.refresh_token = cfg.get("refresh_token")

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.access_token:
            h["Authorization"] = f"Bearer {self.access_token}"
        return h

    def _try_refresh_token(self) -> bool:
        if not self.refresh_token:
            return False
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(
                    f"{self.base_url}/api/auth/refresh",
                    json={"refresh_token": self.refresh_token},
                )
                if res.status_code == 200:
                    data = res.json()
                    self.access_token = data["access_token"]
                    self.refresh_token = data.get("refresh_token", self.refresh_token)
                    config.update_tokens(self.access_token, self.refresh_token)
                    return True
        except Exception:
            pass
        return False

    def request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        json_body: Optional[dict] = None,
        retry_auth: bool = True,
    ) -> Any:
        url = f"{self.base_url}{path}"
        with httpx.Client(timeout=30.0) as client:
            try:
                res = client.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    headers=self._headers(),
                )
            except httpx.RequestError as exc:
                formatters.print_error(f"Failed to connect to API server at {self.base_url}: {exc}")
                raise SystemExit(1)

            if res.status_code == 401 and retry_auth:
                if self._try_refresh_token():
                    return self.request(method, path, params=params, json_body=json_body, retry_auth=False)
                else:
                    formatters.print_error("Session expired or unauthorized. Please run 'mgops login'.")
                    raise SystemExit(1)

            if not (200 <= res.status_code < 300):
                detail = "Request failed"
                try:
                    err_json = res.json()
                    detail = err_json.get("detail", str(err_json))
                except Exception:
                    detail = res.text or f"HTTP {res.status_code}"
                formatters.print_error(f"[{res.status_code}] {detail}")
                raise SystemExit(1)

            if res.status_code == 204 or not res.content:
                return {}
            return res.json()

    def get(self, path: str, params: Optional[dict] = None) -> Any:
        return self.request("GET", path, params=params)

    def post(self, path: str, json_body: Optional[dict] = None) -> Any:
        return self.request("POST", path, json_body=json_body)

    def patch(self, path: str, json_body: Optional[dict] = None) -> Any:
        return self.request("PATCH", path, json_body=json_body)

    def delete(self, path: str) -> Any:
        return self.request("DELETE", path)

    def stream_sse_logs(self, cluster_id: str, job_id: str) -> Generator[str, None, None]:
        url = f"{self.base_url}/api/clusters/{cluster_id}/jobs/{job_id}/stream"
        headers = self._headers()
        with httpx.Client(timeout=None) as client:
            try:
                with client.stream("GET", url, headers=headers) as response:
                    if response.status_code != 200:
                        formatters.print_error(f"Failed to stream logs (HTTP {response.status_code})")
                        return
                    for line in response.iter_lines():
                        if line.startswith("data: "):
                            yield line[6:]
                        elif line and not line.startswith(":"):
                            yield line
            except httpx.RequestError as exc:
                formatters.print_error(f"Log stream disconnected: {exc}")
