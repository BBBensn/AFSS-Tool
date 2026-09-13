import importlib
import sys


def test_wsgi_app_builds_from_env_vars(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    db_path = tmp_path / "test.db"

    monkeypatch.setenv("AFSS_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("AFSS_DB_PATH", str(db_path))
    monkeypatch.setenv("AFSS_SECRET_KEY", "test-secret")

    sys.modules.pop("afss.wsgi", None)
    wsgi = importlib.import_module("afss.wsgi")

    assert wsgi.config_dir == config_dir
    assert wsgi.db_path == db_path
    assert wsgi.app.secret_key == "test-secret"

    resp = wsgi.app.test_client().get("/")
    assert resp.status_code == 200


def test_wsgi_falls_back_to_local_defaults_without_env_vars(monkeypatch):
    monkeypatch.delenv("AFSS_CONFIG_DIR", raising=False)
    monkeypatch.delenv("AFSS_DB_PATH", raising=False)
    monkeypatch.delenv("AFSS_SECRET_KEY", raising=False)

    sys.modules.pop("afss.wsgi", None)
    wsgi = importlib.import_module("afss.wsgi")

    assert wsgi.config_dir == wsgi.Path("config")
    assert wsgi.db_path is None
    assert wsgi.app.secret_key == "afss-local-dashboard"
