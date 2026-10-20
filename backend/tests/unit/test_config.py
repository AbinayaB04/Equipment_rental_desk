import pytest

from app.core.config import Settings


def test_unset_environment_defaults_to_production():
    settings = Settings.from_env({})

    assert settings.app_env == "production"
    assert settings.cors_origins == ()
    assert settings.log_level == "INFO"
    assert settings.allow_test_clock is False
    assert settings.test_clock_key == ""


def test_cors_origins_are_split_and_trimmed():
    settings = Settings.from_env({"CORS_ORIGINS": "http://a.test, http://b.test ,"})

    assert settings.cors_origins == ("http://a.test", "http://b.test")


def test_log_level_is_upper_cased():
    settings = Settings.from_env({"APP_ENV": "development", "LOG_LEVEL": "debug"})

    assert settings.app_env == "development"
    assert settings.log_level == "DEBUG"


def test_startup_production_requires_key_of_at_least_16_chars():
    # APP_ENV unset -> treated as production
    # production + ALLOW_TEST_CLOCK=true + no key -> startup fails
    with pytest.raises(ValueError, match="TEST_CLOCK_KEY"):
        Settings.from_env({"ALLOW_TEST_CLOCK": "true"})

    with pytest.raises(ValueError, match="TEST_CLOCK_KEY"):
        Settings.from_env({"APP_ENV": "production", "ALLOW_TEST_CLOCK": "true"})

    # key shorter than 16 characters -> startup fails
    with pytest.raises(ValueError, match="16"):
        Settings.from_env(
            {
                "APP_ENV": "production",
                "ALLOW_TEST_CLOCK": "true",
                "TEST_CLOCK_KEY": "short-key-12345",  # 15 chars
            }
        )

    # key of 16 or more characters -> starts
    valid_key = "1234567890123456"  # 16 chars
    settings = Settings.from_env(
        {
            "APP_ENV": "production",
            "ALLOW_TEST_CLOCK": "true",
            "TEST_CLOCK_KEY": valid_key,
        }
    )
    assert settings.app_env == "production"
    assert settings.allow_test_clock is True
    assert settings.test_clock_key == valid_key


def test_startup_non_production_allows_test_clock_without_key():
    # development or test + enabled + no key -> starts
    settings_dev = Settings.from_env({"APP_ENV": "development", "ALLOW_TEST_CLOCK": "true"})
    assert settings_dev.app_env == "development"
    assert settings_dev.allow_test_clock is True

    settings_test = Settings.from_env({"APP_ENV": "test", "ALLOW_TEST_CLOCK": "true"})
    assert settings_test.app_env == "test"
    assert settings_test.allow_test_clock is True


def test_startup_production_without_allow_test_clock_starts_disabled():
    # production + ALLOW_TEST_CLOCK unset -> starts, clock disabled
    settings = Settings.from_env({"APP_ENV": "production"})
    assert settings.app_env == "production"
    assert settings.allow_test_clock is False
