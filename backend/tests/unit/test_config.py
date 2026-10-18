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


def test_production_guard_overrides_allow_test_clock_even_with_whitespace():
    # Production guard must override ALLOW_TEST_CLOCK=true even with whitespace/casing
    settings = Settings.from_env(
        {
            "APP_ENV": " production ",
            "ALLOW_TEST_CLOCK": " true ",
        }
    )

    assert settings.app_env == "production"
    assert settings.allow_test_clock is False


def test_test_clock_enabled_in_non_production():
    settings = Settings.from_env(
        {
            "APP_ENV": "development",
            "ALLOW_TEST_CLOCK": "true",
            "TEST_CLOCK_KEY": "secret123",
        }
    )

    assert settings.app_env == "development"
    assert settings.allow_test_clock is True
    assert settings.test_clock_key == "secret123"
