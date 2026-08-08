"""Unit tests for field preferences configuration priority."""

from __future__ import annotations

import json

import pytest

from homebox_companion.core import field_preferences

# All tests in this module are unit tests (use tmp_path, no external services)
pytestmark = pytest.mark.unit


class TestConfigurationPriority:
    """Test the two-tier priority: file overrides > defaults (env + hardcoded)."""

    def test_load_with_no_file_no_env_returns_hardcoded(self, monkeypatch, tmp_path) -> None:
        """With no file and no env vars, should return hardcoded defaults."""
        # Clear all HBC_AI_* env vars
        import os

        for key in list(os.environ.keys()):
            if key.startswith("HBC_AI_"):
                monkeypatch.delenv(key, raising=False)

        # Set up clean config directory
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        monkeypatch.setattr(field_preferences, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(field_preferences, "PREFERENCES_FILE", config_dir / "field_preferences.json")
        field_preferences.get_defaults.cache_clear()

        # Get defaults
        defaults = field_preferences.get_defaults()

        assert defaults.output_language == "English"
        assert "Title Case" in defaults.name
        assert "NEVER mention quantity" in defaults.description

    def test_load_with_env_vars_set_overrides_hardcoded(self, monkeypatch, tmp_path) -> None:
        """Environment variables should override hardcoded defaults."""
        monkeypatch.setenv("HBC_AI_OUTPUT_LANGUAGE", "Spanish")
        monkeypatch.setenv("HBC_AI_NAME", "Custom naming from env")

        config_dir = tmp_path / "config"
        config_dir.mkdir()

        monkeypatch.setattr(field_preferences, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(field_preferences, "PREFERENCES_FILE", config_dir / "field_preferences.json")
        field_preferences.get_defaults.cache_clear()

        defaults = field_preferences.get_defaults()

        assert defaults.output_language == "Spanish"
        assert defaults.name == "Custom naming from env"
        # Non-overridden field still has hardcoded default
        assert "NEVER mention quantity" in defaults.description

    def test_load_with_file_present_overrides_env(self, monkeypatch, tmp_path) -> None:
        """File-based preferences should override environment variables."""
        monkeypatch.setenv("HBC_AI_OUTPUT_LANGUAGE", "French")
        monkeypatch.setenv("HBC_AI_NAME", "Env naming")

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        prefs_file = config_dir / "field_preferences.json"

        # Create file with different values
        file_prefs = {
            "output_language": "German",
            "name": "File-based naming",
            "description": "File description",
        }
        prefs_file.write_text(json.dumps(file_prefs))

        monkeypatch.setattr(field_preferences, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(field_preferences, "PREFERENCES_FILE", prefs_file)
        field_preferences.get_defaults.cache_clear()

        prefs = field_preferences.load_field_preferences()

        # File values should win
        assert prefs.output_language == "German"
        assert prefs.name == "File-based naming"
        assert prefs.description == "File description"


class TestGetEffectiveCustomizations:
    """Test that effective customizations returns all fields."""

    def test_all_fields_have_values(self, monkeypatch) -> None:
        """get_effective_customizations should return all prompt fields."""
        import os

        # Clear env vars
        for key in list(os.environ.keys()):
            if key.startswith("HBC_AI_"):
                monkeypatch.delenv(key, raising=False)

        field_preferences.get_defaults.cache_clear()

        from homebox_companion.core.field_preferences import FieldPreferences

        prefs = FieldPreferences()  # All defaults

        result = prefs.get_effective_customizations()

        expected_fields = [
            "name",
            "description",
            "quantity",
            "manufacturer",
            "model_number",
            "serial_number",
            "purchase_price",
            "purchase_from",
            "notes",
            "naming_examples",
        ]

        for field in expected_fields:
            assert field in result
            assert result[field]  # Has non-empty value

    def test_excludes_metadata_fields(self) -> None:
        """output_language and default_tag_id should be excluded."""
        from homebox_companion.core.field_preferences import FieldPreferences

        prefs = FieldPreferences(
            output_language="Spanish",
            default_tag_id="tag-123",
            name="Custom name",
        )

        result = prefs.get_effective_customizations()

        assert "name" in result
        assert "output_language" not in result
        assert "default_tag_id" not in result

    def test_excludes_disable_tag_suggestions(self) -> None:
        """disable_tag_suggestions is metadata, not a prompt instruction, so it must be excluded."""
        from homebox_companion.core.field_preferences import FieldPreferences

        prefs = FieldPreferences(disable_tag_suggestions=True, name="Custom name")

        result = prefs.get_effective_customizations()

        assert "name" in result
        assert "disable_tag_suggestions" not in result


class TestDisableTagSuggestions:
    """Test the HBC_AI_DISABLE_TAG_SUGGESTIONS toggle."""

    def test_defaults_to_false(self, monkeypatch) -> None:
        """Without the env var set, disable_tag_suggestions should default to False."""
        import os

        from homebox_companion.core.field_preferences import FieldPreferences

        monkeypatch.delenv("HBC_AI_DISABLE_TAG_SUGGESTIONS", raising=False)
        for key in list(os.environ.keys()):
            if key.startswith("HBC_AI_"):
                monkeypatch.delenv(key, raising=False)

        assert FieldPreferences().disable_tag_suggestions is False

    def test_settable_via_env_var(self, monkeypatch) -> None:
        """Setting HBC_AI_DISABLE_TAG_SUGGESTIONS=true should enable the toggle."""
        from homebox_companion.core.field_preferences import FieldPreferences

        monkeypatch.setenv("HBC_AI_DISABLE_TAG_SUGGESTIONS", "true")

        assert FieldPreferences().disable_tag_suggestions is True

    def test_env_wins_over_settings_api_override_attempt(self, monkeypatch, tmp_path) -> None:
        """The operator's env var must win even if a settings-API save tries to flip it."""
        from homebox_companion.core.field_preferences import FieldPreferences

        monkeypatch.setenv("HBC_AI_DISABLE_TAG_SUGGESTIONS", "true")

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        prefs_file = config_dir / "field_preferences.json"

        monkeypatch.setattr(field_preferences, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(field_preferences, "PREFERENCES_FILE", prefs_file)
        field_preferences.get_defaults.cache_clear()

        # Simulate a client attempting to override via the settings API.
        field_preferences.save_field_preferences(FieldPreferences(disable_tag_suggestions=False))

        loaded = field_preferences.load_field_preferences()
        assert loaded.disable_tag_suggestions is True

    def test_save_never_writes_disable_tag_suggestions_key(self, monkeypatch, tmp_path) -> None:
        """save_field_preferences must never persist disable_tag_suggestions, even if non-default."""
        from homebox_companion.core.field_preferences import FieldPreferences

        for key in ("HBC_AI_DISABLE_TAG_SUGGESTIONS",):
            monkeypatch.delenv(key, raising=False)

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        prefs_file = config_dir / "field_preferences.json"

        monkeypatch.setattr(field_preferences, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(field_preferences, "PREFERENCES_FILE", prefs_file)
        field_preferences.get_defaults.cache_clear()

        field_preferences.save_field_preferences(FieldPreferences(disable_tag_suggestions=True))

        saved_data = json.loads(prefs_file.read_text())
        assert "disable_tag_suggestions" not in saved_data

    def test_load_user_overrides_excludes_disable_tag_suggestions(self, monkeypatch, tmp_path) -> None:
        """load_user_overrides must never expose disable_tag_suggestions as user-overridable."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        prefs_file = config_dir / "field_preferences.json"
        prefs_file.write_text(json.dumps({"disable_tag_suggestions": True, "name": "Custom name"}))

        monkeypatch.setattr(field_preferences, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(field_preferences, "PREFERENCES_FILE", prefs_file)
        field_preferences.get_defaults.cache_clear()

        overrides = field_preferences.load_user_overrides()

        assert "disable_tag_suggestions" not in overrides


class TestEnforceOperatorDisableTagSuggestions:
    """Test the helper that forces disable_tag_suggestions to the env-resolved value."""

    def test_env_true_overrides_client_false(self, monkeypatch) -> None:
        """A client-supplied False must be forced to True when the operator has enabled the kill switch."""
        from homebox_companion.core.field_preferences import FieldPreferences

        monkeypatch.setenv("HBC_AI_DISABLE_TAG_SUGGESTIONS", "true")
        field_preferences.get_defaults.cache_clear()

        client_prefs = FieldPreferences(disable_tag_suggestions=False)
        result = field_preferences.enforce_operator_disable_tag_suggestions(client_prefs)

        assert result.disable_tag_suggestions is True

        field_preferences.get_defaults.cache_clear()

    def test_env_false_overrides_client_true(self, monkeypatch) -> None:
        """A client-supplied True must be forced to False when the operator hasn't enabled the kill switch."""
        from homebox_companion.core.field_preferences import FieldPreferences

        monkeypatch.delenv("HBC_AI_DISABLE_TAG_SUGGESTIONS", raising=False)
        field_preferences.get_defaults.cache_clear()

        client_prefs = FieldPreferences(disable_tag_suggestions=True)
        result = field_preferences.enforce_operator_disable_tag_suggestions(client_prefs)

        assert result.disable_tag_suggestions is False

        field_preferences.get_defaults.cache_clear()

    def test_preserves_other_fields(self, monkeypatch) -> None:
        """Only disable_tag_suggestions should be overwritten; other fields pass through unchanged."""
        from homebox_companion.core.field_preferences import FieldPreferences

        monkeypatch.setenv("HBC_AI_DISABLE_TAG_SUGGESTIONS", "true")
        field_preferences.get_defaults.cache_clear()

        client_prefs = FieldPreferences(disable_tag_suggestions=False, name="Custom name")
        result = field_preferences.enforce_operator_disable_tag_suggestions(client_prefs)

        assert result.name == "Custom name"

        field_preferences.get_defaults.cache_clear()


class TestResetPreferences:
    """Test resetting preferences to defaults."""

    def test_reset_deletes_file_and_returns_defaults(self, monkeypatch, tmp_path) -> None:
        """Reset should delete file and return defaults (not None values)."""
        monkeypatch.setenv("HBC_AI_OUTPUT_LANGUAGE", "Italian")
        monkeypatch.setenv("HBC_AI_NAME", "Env name")

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        prefs_file = config_dir / "field_preferences.json"

        # Create file that will be deleted
        file_prefs = {"output_language": "Japanese", "name": "File name"}
        prefs_file.write_text(json.dumps(file_prefs))
        assert prefs_file.exists()

        monkeypatch.setattr(field_preferences, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(field_preferences, "PREFERENCES_FILE", prefs_file)
        field_preferences.get_defaults.cache_clear()

        prefs = field_preferences.reset_field_preferences()

        # File should be deleted
        assert not prefs_file.exists()

        # Should return defaults (env vars applied)
        assert prefs.output_language == "Italian"  # From env
        assert prefs.name == "Env name"  # From env

    def test_reset_without_file_succeeds(self, monkeypatch, tmp_path) -> None:
        """Reset should succeed even if no file exists."""
        monkeypatch.setenv("HBC_AI_OUTPUT_LANGUAGE", "German")

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        prefs_file = config_dir / "field_preferences.json"

        assert not prefs_file.exists()

        monkeypatch.setattr(field_preferences, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(field_preferences, "PREFERENCES_FILE", prefs_file)
        field_preferences.get_defaults.cache_clear()

        # Should not raise error
        prefs = field_preferences.reset_field_preferences()

        # Returns defaults
        assert prefs.output_language == "German"  # From env


class TestSaveAndLoad:
    """Test save/load round-trip."""

    def test_save_and_load_preserves_values(self, monkeypatch, tmp_path) -> None:
        """Saved preferences should load correctly."""
        from homebox_companion.core.field_preferences import FieldPreferences

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        prefs_file = config_dir / "field_preferences.json"

        monkeypatch.setattr(field_preferences, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(field_preferences, "PREFERENCES_FILE", prefs_file)
        field_preferences.get_defaults.cache_clear()

        # Save preferences
        prefs = FieldPreferences(
            output_language="Portuguese",
            name="Custom name instruction",
            description="Custom description",
        )
        field_preferences.save_field_preferences(prefs)

        assert prefs_file.exists()

        # Load them back
        loaded = field_preferences.load_field_preferences()

        assert loaded.output_language == "Portuguese"
        assert loaded.name == "Custom name instruction"
        assert loaded.description == "Custom description"

    def test_save_creates_config_dir(self, monkeypatch, tmp_path) -> None:
        """Save should create config directory if it doesn't exist."""
        from homebox_companion.core.field_preferences import FieldPreferences

        config_dir = tmp_path / "nonexistent" / "config"
        prefs_file = config_dir / "field_preferences.json"

        monkeypatch.setattr(field_preferences, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(field_preferences, "PREFERENCES_FILE", prefs_file)

        assert not config_dir.exists()

        prefs = FieldPreferences(name="Test")
        field_preferences.save_field_preferences(prefs)

        assert config_dir.exists()
        assert prefs_file.exists()

    def test_save_sparse_format(self, monkeypatch, tmp_path) -> None:
        """Save should only write fields that differ from defaults (sparse)."""
        from homebox_companion.core.field_preferences import FieldPreferences

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        prefs_file = config_dir / "field_preferences.json"

        monkeypatch.setattr(field_preferences, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(field_preferences, "PREFERENCES_FILE", prefs_file)
        field_preferences.get_defaults.cache_clear()

        # Create preferences with only name customized
        defaults = field_preferences.get_defaults()
        prefs = FieldPreferences(
            output_language=defaults.output_language,  # Same as default
            name="Custom name",  # Different from default
            description=defaults.description,  # Same as default
        )
        field_preferences.save_field_preferences(prefs)

        # Load the JSON and verify sparse format
        saved_data = json.loads(prefs_file.read_text())
        assert "name" in saved_data
        assert saved_data["name"] == "Custom name"
        # Fields matching defaults should NOT be in the file
        assert "output_language" not in saved_data
        assert "description" not in saved_data
