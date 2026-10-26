"""
Tests for sensitive word migration to llm-compat.

Verifies:
- LLMConfig no longer has risk_* fields or select_models_for_task
- coordinator.process() no longer accepts has_risk parameter
- set_default_config() passes SensitiveDetector to SyncLLMClient
- _detect_risk function is removed from llm_ops

All console output must be in English only (no emoji, no Chinese).
"""

import pytest
from unittest.mock import patch, MagicMock


class TestLLMConfigRiskFieldsRemoved:
    """LLMConfig should no longer have risk model fields."""

    def test_no_risk_calibrate_model_field(self):
        """LLMConfig should not have risk_calibrate_model field."""
        from video_transcript_api.llm.core.config import LLMConfig
        config = LLMConfig(
            api_key="k", base_url="u",
            calibrate_model="m", summary_model="s",
        )
        assert not hasattr(config, "risk_calibrate_model")

    def test_no_risk_summary_model_field(self):
        """LLMConfig should not have risk_summary_model field."""
        from video_transcript_api.llm.core.config import LLMConfig
        config = LLMConfig(
            api_key="k", base_url="u",
            calibrate_model="m", summary_model="s",
        )
        assert not hasattr(config, "risk_summary_model")

    def test_no_enable_risk_model_selection_field(self):
        """LLMConfig should not have enable_risk_model_selection field."""
        from video_transcript_api.llm.core.config import LLMConfig
        config = LLMConfig(
            api_key="k", base_url="u",
            calibrate_model="m", summary_model="s",
        )
        assert not hasattr(config, "enable_risk_model_selection")

    def test_no_select_models_for_task_method(self):
        """LLMConfig should not have select_models_for_task method."""
        from video_transcript_api.llm.core.config import LLMConfig
        assert not hasattr(LLMConfig, "select_models_for_task")

    def test_from_dict_ignores_risk_fields(self):
        """from_dict should work even if config has old risk fields."""
        from video_transcript_api.llm.core.config import LLMConfig
        config_dict = {
            "llm": {
                "api_key": "k", "base_url": "u",
                "calibrate_model": "m", "summary_model": "s",
                "risk_calibrate_model": "old-risk-model",
                "enable_risk_model_selection": True,
            }
        }
        config = LLMConfig.from_dict(config_dict)
        assert config.calibrate_model == "m"
        assert not hasattr(config, "risk_calibrate_model")


class TestCoordinatorNoHasRisk:
    """coordinator.process() should not accept has_risk parameter."""

    def test_process_signature_no_has_risk(self):
        """process() should not have has_risk in its signature."""
        import inspect
        from video_transcript_api.llm.coordinator import LLMCoordinator
        sig = inspect.signature(LLMCoordinator.process)
        assert "has_risk" not in sig.parameters


class TestSensitiveDetectorIntegration:
    """set_default_config should pass SensitiveDetector to SyncLLMClient."""

    @patch("video_transcript_api.llm.llm.SyncLLMClient")
    def test_sensitive_detector_passed_when_words_available(self, mock_client_cls):
        """When risk_control words are available, SensitiveDetector should be passed."""
        from video_transcript_api.llm.llm import set_default_config

        config = {
            "llm": {
                "api_key": "test-key",
                "base_url": "https://api.test.com/v1",
            },
            "risk_control": {
                "enabled": True,
                "sensitive_word_urls": ["https://example.com/words.txt"],
                "cache_file": "/tmp/test_words.txt",
            },
        }

        with patch(
            "video_transcript_api.risk_control.sensitive_words_manager.SensitiveWordsManager.load_words",
            return_value={"word1", "word2"},
        ), patch(
            "video_transcript_api.risk_control.sensitive_words_manager.SensitiveWordsManager.__init__",
            return_value=None,
        ):
            set_default_config(config)

            call_kwargs = mock_client_cls.call_args[1]
            assert "sensitive_detector" in call_kwargs
            assert call_kwargs["sensitive_detector"] is not None

    @patch("video_transcript_api.llm.llm.SyncLLMClient")
    def test_no_detector_when_risk_control_disabled(self, mock_client_cls):
        """When risk_control is disabled, no SensitiveDetector should be passed."""
        from video_transcript_api.llm.llm import set_default_config

        config = {
            "llm": {
                "api_key": "test-key",
                "base_url": "https://api.test.com/v1",
            },
            "risk_control": {
                "enabled": False,
            },
        }

        set_default_config(config)

        call_kwargs = mock_client_cls.call_args[1]
        sd = call_kwargs.get("sensitive_detector")
        assert sd is None

    @patch("video_transcript_api.llm.llm.SyncLLMClient")
    def test_no_detector_when_no_risk_control_config(self, mock_client_cls):
        """When risk_control config is missing, no SensitiveDetector."""
        from video_transcript_api.llm.llm import set_default_config

        config = {
            "llm": {
                "api_key": "test-key",
                "base_url": "https://api.test.com/v1",
            },
        }

        set_default_config(config)

        call_kwargs = mock_client_cls.call_args[1]
        sd = call_kwargs.get("sensitive_detector")
        assert sd is None


class TestDetectRiskRemoved:
    """_detect_risk function should be removed from llm_ops."""

    def test_no_detect_risk_function(self):
        """llm_ops should not have _detect_risk function."""
        from video_transcript_api.api.services import llm_ops
        assert not hasattr(llm_ops, "_detect_risk")
