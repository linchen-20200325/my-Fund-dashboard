"""Pure stdlib tests for conservative static-import triage."""
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.audit_static_reachability import scan


def test_relative_import_and_unreferenced_module():
    with TemporaryDirectory() as d:
        root = Path(d)
        (root / "services" / "pkg").mkdir(parents=True)
        for path, content in {
            "__init__.py": "",
            "pkg/__init__.py": "",
            "pkg/used.py": "VALUE=1",
            "pkg/unreferenced.py": "VALUE=2",
            "pkg/consumer.py": "from . import used\n",
        }.items():
            (root / "services" / path).write_text(content)
        report = scan(root)
        assert "services.pkg.used" in report["imports"]["services.pkg.consumer"]
        names = [x["module"] for x in report["without_static_importers"]]
        assert "services.pkg.unreferenced" in names
        assert "services.pkg.used" not in names


def test_dynamic_import_and_no_deletion_claim():
    with TemporaryDirectory() as d:
        root = Path(d)
        (root / "services").mkdir()
        (root / "services" / "a.py").write_text(
            'import importlib\nimportlib.import_module("services.b")\n'
        )
        (root / "services" / "b.py").write_text("VALUE=2\n")
        report = scan(root)
        assert report["classification"] == "TRIAGE_ONLY_NOT_SAFE_TO_DELETE"
        assert report["dynamic_import_sites"] == [{"module": "services.a", "lines": [2]}]


def test_discover_new_ui_generation_without_hardcoded_path():
    with TemporaryDirectory() as d:
        root = Path(d)
        (root / "ui_v42").mkdir()
        (root / "ui_v42" / "app_preview.py").write_text("VALUE=1\n")
        report = scan(root)
        assert report["external_entrypoints_to_verify"] == ["app.py", "ui_v42/app_preview.py"]
        assert report["module_count"] == 1


def test_root_modules_and_unlisted_packages_are_not_silently_omitted(tmp_path):
    sources = {
        "app.py": "import fund_fetcher\n",
        "fund_fetcher.py": "from models.record import VALUE\n",
        "models/record.py": "VALUE = 1\n",
        "mcp_server/server.py": "import fund_fetcher\n",
        "future_package/consumer.py": "from models import record\n",
    }
    for name, source in sources.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    report = scan(tmp_path)
    assert report["scanned_paths"] == sorted(sources)
    assert "fund_fetcher" in report["imports"]["app"]
    assert "models.record" in report["imports"]["fund_fetcher"]
    assert "fund_fetcher" in report["imports"]["mcp_server.server"]
    assert "models.record" in report["imports"]["future_package.consumer"]


def test_environment_hidden_and_linked_sources_are_excluded(tmp_path):
    for directory in (".git", ".claude/worktrees/copy", ".venv", "venv", "node_modules", "__pycache__"):
        path = tmp_path / directory / "broken.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("invalid python!", encoding="utf-8")
    real = tmp_path / "real.py"
    real.write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "linked.py").symlink_to(real)
    (tmp_path / "linked_directory").symlink_to(tmp_path / "venv", target_is_directory=True)
    report = scan(tmp_path)
    assert report["scanned_paths"] == ["real.py"]
    assert report["parse_errors"] == {}
