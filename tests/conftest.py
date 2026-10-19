import pytest

import auth
from tests.tokens import AUDIENCE, TENANT, FakeJwks


@pytest.fixture
def auth_env(monkeypatch):
    """Configure authentication for a test: our tenant/audience and a fake key server (no network)."""
    monkeypatch.setenv("AZURE_TENANT_ID", TENANT)
    monkeypatch.setenv("API_AUDIENCE", AUDIENCE)
    monkeypatch.setattr(auth, "_jwks_client", lambda tenant_id: FakeJwks())
