"""Tests for server.dependencies, in particular get_vision_context."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from homebox_companion.core import field_preferences

# All tests in this module are unit tests (no external services)
pytestmark = pytest.mark.unit


class TestGetVisionContextDisableTagSuggestions:
    """The operator's HBC_AI_DISABLE_TAG_SUGGESTIONS kill switch must win over any
    client-supplied value, including via the X-Field-Preferences demo-mode header."""

    @pytest.mark.asyncio
    async def test_header_cannot_re_enable_tags_when_operator_disabled(self, monkeypatch) -> None:
        """A client sending disable_tag_suggestions=false via header must not re-enable tag fetching."""
        from server.dependencies import get_vision_context

        monkeypatch.setenv("HBC_AI_DISABLE_TAG_SUGGESTIONS", "true")
        field_preferences.get_defaults.cache_clear()

        mock_get_tags = AsyncMock(return_value=[{"id": "abc", "name": "Electronics"}])

        with patch("server.dependencies.get_tags_for_context", mock_get_tags):
            ctx = await get_vision_context(
                authorization="Bearer faketoken",
                x_field_preferences=json.dumps({"disable_tag_suggestions": False}),
            )

        mock_get_tags.assert_not_called()
        assert ctx.tags == []

        field_preferences.get_defaults.cache_clear()

    @pytest.mark.asyncio
    async def test_no_header_and_operator_enabled_fetches_tags(self, monkeypatch) -> None:
        """Sanity check: without the env kill switch, tags are fetched as normal."""
        from server.dependencies import get_vision_context

        monkeypatch.delenv("HBC_AI_DISABLE_TAG_SUGGESTIONS", raising=False)
        field_preferences.get_defaults.cache_clear()

        mock_get_tags = AsyncMock(return_value=[{"id": "abc", "name": "Electronics"}])

        with patch("server.dependencies.get_tags_for_context", mock_get_tags):
            ctx = await get_vision_context(authorization="Bearer faketoken")

        mock_get_tags.assert_called_once()
        assert ctx.tags == [{"id": "abc", "name": "Electronics"}]

        field_preferences.get_defaults.cache_clear()
