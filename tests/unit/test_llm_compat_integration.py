"""llm-compat integration tests

Verifies error mapping, config parsing, and fallback logging
for the llm-compat migration.
"""

import logging
from unittest.mock import MagicMock, patch

import pytest

from llm_compat import (
    ContentPolicyError,
    FatalError as LLMCompatFatalError,
    JSONParseError,
    TimeoutError as LLMCompatTimeoutError,
)

from video_transcript_api.llm.core.errors import (
    FatalError,
    RetryableError,
    TimeoutError,
    TruncationError,
    classify_error,
    map_llm_compat_error,
)
from video_transcript_api.llm.core.config import LLMConfig


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------


class TestMapLLMCompatError:
    """map_llm_compat_error translates llm-compat exceptions to project types."""

    def test_fatal_error_mapped(self):
        err = LLMCompatFatalError("401 Unauthorized")
        result = map_llm_compat_error(err)
        assert isinstance(result, FatalError)

    def test_timeout_error_mapped(self):
        err = LLMCompatTimeoutError("Request timed out")
        result = map_llm_compat_error(err)
        assert isinstance(result, TimeoutError)

    def test_json_parse_error_mapped(self):
        err = JSONParseError("Invalid JSON", raw_content="{bad", model="test", request_id="r1")
        result = map_llm_compat_error(err)
        assert isinstance(result, TruncationError)

    def test_content_policy_error_mapped_to_retryable(self):
        err = ContentPolicyError(
            "All models refused",
            attempted_models=["deepseek-v4", "gemini-3-flash"],
            raw_content="I cannot assist",
            original_model="deepseek-v4",
        )
        result = map_llm_compat_error(err)
        assert isinstance(result, RetryableError)
        assert not isinstance(result, FatalError)

    def test_generic_exception_mapped_to_retryable(self):
        err = RuntimeError("Something went wrong")
        result = map_llm_compat_error(err)
        assert isinstance(result, RetryableError)


# ---------------------------------------------------------------------------
# Config parsing: content_fallbacks / collector
# ---------------------------------------------------------------------------


class TestConfigContentFallbacks:
    """LLMConfig.from_dict parses content_fallbacks and collector fields."""

    @staticmethod
    def _base_config(**overrides):
        llm = {
            "api_key": "sk-test",
            "base_url": "https://api.example.com/v1",
            "calibrate_model": "deepseek-v4",
            "summary_model": "deepseek-v4-flash",
        }
        llm.update(overrides)
        return {"llm": llm}

    def test_content_fallbacks_parsed(self):
        cfg = self._base_config(content_fallbacks={
            "deepseek-v4": ["gemini-3-flash-preview", "gemini-2.5-flash"],
        })
        config = LLMConfig.from_dict(cfg)
        assert config.content_fallbacks == {
            "deepseek-v4": ["gemini-3-flash-preview", "gemini-2.5-flash"],
        }

    def test_content_fallbacks_default_none(self):
        cfg = self._base_config()
        config = LLMConfig.from_dict(cfg)
        assert config.content_fallbacks is None

    def test_collector_url_parsed(self):
        cfg = self._base_config(
            collector_url="http://collector:8000",
            collector_project="video-api",
            collector_api_key="key123",
        )
        config = LLMConfig.from_dict(cfg)
        assert config.collector_url == "http://collector:8000"
        assert config.collector_project == "video-api"
        assert config.collector_api_key == "key123"

    def test_collector_defaults_empty(self):
        cfg = self._base_config()
        config = LLMConfig.from_dict(cfg)
        assert config.collector_url is None
        assert config.collector_project == ""
        assert config.collector_api_key == ""

    def test_refusal_keywords_url_parsed(self):
        cfg = self._base_config(
            refusal_keywords_url="http://collector:8000/words",
        )
        config = LLMConfig.from_dict(cfg)
        assert config.refusal_keywords_url == "http://collector:8000/words"

    def test_total_timeout_parsed(self):
        cfg = self._base_config(total_timeout=180.0)
        config = LLMConfig.from_dict(cfg)
        assert config.total_timeout == 180.0

    def test_total_timeout_default(self):
        cfg = self._base_config()
        config = LLMConfig.from_dict(cfg)
        assert config.total_timeout == 300.0
