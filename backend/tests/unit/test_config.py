from app.core.config import Settings


def test_unset_environment_defaults_to_production():
    settings = Settings.from_env({})

    assert settings.app_env == "production"
    assert settings.cors_origins == ()
    assert settings.log_level == "INFO"


def test_cors_origins_are_split_and_trimmed():
    settings = Settings.from_env({"CORS_ORIGINS": "http://a.test, http://b.test ,"})

    assert settings.cors_origins == ("http://a.test", "http://b.test")


def test_log_level_is_upper_cased():
    settings = Settings.from_env({"APP_ENV": "development", "LOG_LEVEL": "debug"})

    assert settings.app_env == "development"
    assert settings.log_level == "DEBUG"
