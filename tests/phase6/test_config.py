from pathlib import Path

from src.wrapper.config import WrapperConfig, load_config

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_load_config_parses_all_fields(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "current_saga: 2\n"
        "current_arc: 3\n"
        "backpressure_max_unapproved: 4\n"
        "proposal_backlog_max: 5\n"
        "max_revision_loops: 6\n",
        encoding="utf-8",
    )
    config = load_config(config_path)
    assert config == WrapperConfig(
        current_saga=2,
        current_arc=3,
        backpressure_max_unapproved=4,
        proposal_backlog_max=5,
        max_revision_loops=6,
    )


def test_real_repo_config_has_expected_defaults():
    config = load_config(REPO_ROOT / "config.yaml")
    assert config.current_saga == 1
    assert config.current_arc == 1
    assert config.backpressure_max_unapproved == 2
    assert config.proposal_backlog_max == 5
    assert config.max_revision_loops == 3
