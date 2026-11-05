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
