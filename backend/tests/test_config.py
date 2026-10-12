from pathlib import Path

from app.core.config import Settings


def test_settings_paths_are_independent_of_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    settings = Settings(
        _env_file=None,
        database_url="sqlite:///./test.db",
        registry_deployment_file="../contracts/deployments/localhost.json",
    )

    backend_root = Path(__file__).resolve().parents[1]
    assert Path(Settings.model_config["env_file"]) == backend_root / ".env"
    assert settings.database_url == f"sqlite:///{backend_root / 'test.db'}"
    assert settings.registry_deployment_file == str(backend_root.parent / "contracts/deployments/localhost.json")