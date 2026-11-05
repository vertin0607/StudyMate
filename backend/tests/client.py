"""测试客户端。业务测试默认以 local 登录；隔离测试使用不自动登录的客户端。"""

from fastapi.testclient import TestClient as RawTestClient

LOCAL_PASSWORD = "local1234"
_UNSAFE = {"post", "put", "patch", "delete"}


def _business_path(url: str) -> bool:
    path = url.split("?", 1)[0]
    return path.startswith("/api/") and not path.startswith("/api/auth") and not path.startswith("/api/health")


class BusinessTestClient(RawTestClient):
    """沿用原有测试。它们创建的数据属于 local，因此这里用测试库中的 local 登录。"""

    def request(self, method, url, **kwargs):
        if _business_path(url) and not self.cookies.get("studymate_session"):
            self._login_local()
        if _business_path(url) and method.lower() in _UNSAFE:
            headers = dict(kwargs.get("headers") or {})
            if not any(str(key).lower() == "x-csrf-token" for key in headers):
                headers["X-CSRF-Token"] = self.cookies.get("studymate_csrf")
                kwargs["headers"] = headers
        return super().request(method, url, **kwargs)

    def _login_local(self) -> None:
        csrf = super().request("GET", "/api/auth/csrf")
        token = csrf.json()["csrf_token"]
        response = super().request(
            "POST",
            "/api/auth/login",
            json={"username": "local", "password": LOCAL_PASSWORD},
            headers={"X-CSRF-Token": token},
        )
        if response.status_code != 200:
            raise AssertionError(response.text)
