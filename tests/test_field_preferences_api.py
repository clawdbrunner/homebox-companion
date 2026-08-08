"""Tests for the field preferences API routes."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# All tests in this module are unit tests (use tmp_path, no external services)
pytestmark = pytest.mark.unit


@pytest.fixture
def field_preferences_test_client() -> TestClient:
    """Build a minimal FastAPI app mounting only the field_preferences router, auth bypassed."""
    from server.api import field_preferences as field_preferences_api
    from server.dependencies import get_token

    app = FastAPI()
    app.include_router(field_preferences_api.router)
    app.dependency_overrides[get_token] = lambda: "fake-token"
    return TestClient(app)


class TestPromptPreview:
    """Test the /settings/prompt-preview endpoint."""

    def test_disable_tag_suggestions_omits_example_tags(
        self, field_preferences_test_client: TestClient
    ) -> None:
        """When disable_tag_suggestions is True, the preview must not contain example tag names."""
        response = field_preferences_test_client.post(
            "/settings/prompt-preview",
            json={
                "field_preferences": {"disable_tag_suggestions": True},
                "custom_fields": [],
            },
        )

        assert response.status_code == 200
        prompt = response.json()["prompt"]

        for tag_name in ("Electronics", "Tools", "Supplies"):
            assert tag_name not in prompt

    def test_enabled_tag_suggestions_includes_example_tags(
        self, field_preferences_test_client: TestClient
    ) -> None:
        """When disable_tag_suggestions is False, the preview should show the example tags."""
        response = field_preferences_test_client.post(
            "/settings/prompt-preview",
            json={
                "field_preferences": {"disable_tag_suggestions": False},
                "custom_fields": [],
            },
        )

        assert response.status_code == 200
        prompt = response.json()["prompt"]

        assert "Electronics" in prompt
