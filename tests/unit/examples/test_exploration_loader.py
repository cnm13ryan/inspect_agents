import importlib.util
import os


def _load_loader_module() -> object:
    path = os.path.join(os.getcwd(), "examples/inspect/exploration/config_loader.py")
    spec = importlib.util.spec_from_file_location("examples.inspect.exploration.config_loader", path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    assert spec and spec.loader
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_yaml_loader_reads_defaults_and_returns_config(tmp_path):
    mod = _load_loader_module()

    # Prepare a minimal YAML with top-level keys
    yaml_path = tmp_path / "exploration.yaml"
    yaml_path.write_text(
        """
breadth: 2
depth: 1
convergence_delta: 0.1
max_queries: 5
synonym_expansion: false
site_hints: ["arxiv.org", "*.edu"]
        """.strip()
    )

    cfg = mod.load_exploration_config(str(yaml_path))
    assert cfg.breadth == 2
    assert cfg.depth == 1
    assert cfg.max_queries == 5
    assert cfg.synonym_expansion is False
    assert cfg.site_hints == ["arxiv.org", "*.edu"]

    # Now nested under policy:
    yaml_path.write_text(
        """
policy:
  breadth: 3
  depth: 2
  max_queries: 7
  convergence_delta: 0.05
  synonym_expansion: true
  site_hints:
    - arxiv.org
    - "*.gov"
        """.strip()
    )
    cfg2 = mod.load_exploration_config(str(yaml_path))
    assert cfg2.breadth == 3
    assert cfg2.depth == 2
    assert cfg2.max_queries == 7
    assert cfg2.synonym_expansion is True
    assert cfg2.site_hints == ["arxiv.org", "*.gov"]
