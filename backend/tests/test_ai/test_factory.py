import pytest

from app.ai.factory import UnsupportedAIProviderError, create_ai_provider
from app.ai.fake import FakeAIProvider
from app.config import Settings


def test_command_interpretation_is_disabled_by_default():
    settings = Settings(_env_file=None)

    assert create_ai_provider(settings) is None


def test_enabled_fake_provider_is_created_from_settings():
    settings = Settings(
        _env_file=None,
        ai_command_interpretation_enabled=True,
        ai_provider="fake",
    )

    assert isinstance(create_ai_provider(settings), FakeAIProvider)


def test_enabled_fake_provider_is_rejected_in_production():
    settings = Settings(
        _env_file=None,
        app_env="production",
        ai_command_interpretation_enabled=True,
        ai_provider="fake",
    )

    with pytest.raises(UnsupportedAIProviderError, match="not allowed in production"):
        create_ai_provider(settings)


def test_disabled_fake_provider_is_safe_in_production_configuration():
    settings = Settings(
        _env_file=None,
        app_env="production",
        ai_command_interpretation_enabled=False,
        ai_provider="fake",
    )

    assert create_ai_provider(settings) is None


@pytest.mark.parametrize("provider_name", ["anthropic"])
def test_unimplemented_real_provider_fails_closed(provider_name):
    settings = Settings(
        _env_file=None,
        ai_command_interpretation_enabled=True,
        ai_provider=provider_name,
    )

    with pytest.raises(UnsupportedAIProviderError, match="not implemented"):
        create_ai_provider(settings)


def test_unknown_provider_name_is_rejected_by_settings():
    with pytest.raises(ValueError):
        Settings(_env_file=None, ai_provider="unknown")


@pytest.mark.parametrize("environment", ["production", "test", "staging"])
def test_openai_rejected_outside_development(environment):
    settings = Settings(
        _env_file=None,
        app_env=environment,
        ai_provider="openai",
        ai_command_interpretation_enabled=True,
    )
    with pytest.raises(UnsupportedAIProviderError, match="development-only"):
        create_ai_provider(settings)


@pytest.mark.parametrize("key,model", [("", "model"), ("key", ""), (" ", "model")])
def test_openai_requires_explicit_configuration(key, model):
    settings = Settings(
        _env_file=None,
        app_env="development",
        ai_provider="openai",
        ai_command_interpretation_enabled=True,
        openai_api_key=key,
        ai_model=model,
    )
    with pytest.raises(UnsupportedAIProviderError, match="requires"):
        create_ai_provider(settings)


def test_openai_factory_and_secret_redaction():
    from app.ai.openai import OpenAIProvider

    settings = Settings(
        _env_file=None,
        app_env="development",
        ai_provider="openai",
        ai_command_interpretation_enabled=True,
        openai_api_key="test-secret",
        ai_model="model",
    )
    assert isinstance(create_ai_provider(settings), OpenAIProvider)
    assert "test-secret" not in repr(settings)
