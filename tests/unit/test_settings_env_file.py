"""`.env` must reach the nested LLM settings, not just the top-level ones."""

from __future__ import annotations

import os
from pathlib import Path

from negotium.app.settings import Settings


def _write_env(tmp_path: Path) -> Path:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "NG_ARCHIVE_DIR=./from-env-archive",
                "NG_SOLAR_API_KEY=up_from_env_file",
                "NG_SOLAR_MODEL=solar-pro2",
                "NG_LLM_AGENT_TOOLS=true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return env_file


def test_env_file_reaches_nested_llm_settings(tmp_path: Path, monkeypatch) -> None:
    """A nested BaseSettings does not inherit its parent's ``env_file``.

    Without an explicit ``env_file`` on ``LlmSettings`` every documented
    ``NG_SOLAR_*``/``NG_OPENAI_*`` line in ``.env`` was silently ignored — the
    README's setup instructions simply did not work, and the user saw
    "api key is not configured" with no clue why.
    """

    env_file = _write_env(tmp_path)
    # Make sure the values come from the file, not the ambient environment.
    for name in ("NG_SOLAR_API_KEY", "NG_SOLAR_MODEL", "NG_LLM_AGENT_TOOLS", "NG_ARCHIVE_DIR"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)

    settings = Settings(_env_file=str(env_file))

    assert settings.llm.solar_api_key == "up_from_env_file"
    assert settings.llm.solar_model == "solar-pro2"
    assert settings.llm.agent_tools_enabled is True
    # The top-level settings kept working all along; assert it still does.
    assert str(settings.archive_dir) == "from-env-archive"


def test_real_environment_still_wins_over_the_env_file(tmp_path: Path, monkeypatch) -> None:
    env_file = _write_env(tmp_path)
    monkeypatch.setenv("NG_SOLAR_MODEL", "solar-open2")
    monkeypatch.chdir(tmp_path)

    settings = Settings(_env_file=str(env_file))

    assert settings.llm.solar_model == "solar-open2"
    assert os.environ["NG_SOLAR_MODEL"] == "solar-open2"


def test_agent_tools_default_off(monkeypatch, tmp_path: Path) -> None:
    """The tool loop must stay opt-in."""

    monkeypatch.delenv("NG_LLM_AGENT_TOOLS", raising=False)
    monkeypatch.chdir(tmp_path)

    assert Settings(_env_file=None).llm.agent_tools_enabled is False
