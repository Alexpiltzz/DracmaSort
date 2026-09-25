"""Testes unitários para armazenamento seguro de credenciais via keyring."""

from __future__ import annotations

from delivery.smtp import SmtpConfig, get_secure_password, save_secure_password


def test_save_and_get_secure_password(monkeypatch):
    storage = {}

    class DummyKeyring:
        @staticmethod
        def set_password(service, username, password):
            storage[(service, username)] = password

        @staticmethod
        def get_password(service, username):
            return storage.get((service, username))

    monkeypatch.setattr("keyring.set_password", DummyKeyring.set_password)
    monkeypatch.setattr("keyring.get_password", DummyKeyring.get_password)

    ok = save_secure_password("usuario@teste.com", "senha_secreta_123")
    assert ok is True
    assert get_secure_password("usuario@teste.com") == "senha_secreta_123"


def test_save_secure_password_com_dados_invalidos():
    assert save_secure_password("", "senha") is False
    assert save_secure_password("login", "") is False


def test_get_secure_password_com_login_vazio():
    assert get_secure_password("") == ""


def test_smtp_config_from_env_fallback_keyring(monkeypatch):
    monkeypatch.setenv("GIVEAWAY_SMTP_LOGIN", "admin@escola.com")
    monkeypatch.delenv("GIVEAWAY_SMTP_PASS", raising=False)

    class DummyKeyring:
        @staticmethod
        def get_password(service, username):
            if username == "admin@escola.com":
                return "senha_keyring"
            return None

    monkeypatch.setattr("keyring.get_password", DummyKeyring.get_password)

    config = SmtpConfig.from_env()
    assert config.login == "admin@escola.com"
    assert config.password == "senha_keyring"
