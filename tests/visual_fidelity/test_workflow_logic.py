# -*- coding: utf-8 -*-
"""`.github/workflows/pr-check.yml` 的 Visual Fidelity job 守衛（BL-0525 Batch A；fast lane，只解析 YAML）。

釘住：job 存在且非阻擋、artifact 名稱與 `config.CI_ARTIFACT_NAME` 一致（標示「NOT-production-cloud」不得被改掉）、
Cloud capture 預設不跑（只在 workflow_dispatch）、沒有任何外部網路取數步驟、action 版本固定在既有用的 major。
"""

from __future__ import annotations

import pathlib
import sys

import pytest
import yaml

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import config  # noqa: E402

_WF = _HERE.parents[1] / ".github" / "workflows" / "pr-check.yml"
_JOB = "visual-fidelity-safety-net"


@pytest.fixture(scope="module")
def job():
    data = yaml.safe_load(_WF.read_text(encoding="utf-8"))
    assert _JOB in data["jobs"], list(data["jobs"])
    return data["jobs"][_JOB]


def test_job_非阻擋_且不拖慢fast_lane(job):
    assert job["continue-on-error"] is True
    assert job["needs"] == "fast-checks"        # 排在 fast lane 之後；fast lane 本身不含這個 job


def test_artifact名稱帶NOT_production標示_與config一致(job):
    uploads = [s for s in job["steps"] if str(s.get("uses", "")).startswith("actions/upload-artifact@")]
    names = [s["with"]["name"] for s in uploads]
    assert config.CI_ARTIFACT_NAME in names
    ci = next(s for s in uploads if s["with"]["name"] == config.CI_ARTIFACT_NAME)
    assert ci["if"] == "always()" and ci["uses"] == "actions/upload-artifact@v4"
    assert ci["with"]["path"].startswith("visual-fidelity-out/ci-fixture")
    cloud = [s for s in uploads if s["with"]["name"] != config.CI_ARTIFACT_NAME]
    assert [s["with"]["name"] for s in cloud] == ["cloud-preview-screenshots-production-like"]
    assert all(s["if"] == "github.event_name == 'workflow_dispatch'" for s in cloud)


def test_Cloud_capture預設不跑_只在手動dispatch(job):
    steps = [s for s in job["steps"] if "cloud_capture.py" in str(s.get("run", ""))]
    assert len(steps) == 1 and steps[0]["if"] == "github.event_name == 'workflow_dispatch'"


def test_截圖步驟設了輸出目錄_且沒有外部網路取數步驟(job):
    shot = next(s for s in job["steps"] if "test_ci_fixture_screenshots.py" in str(s.get("run", "")))
    assert config.ENV_OUT_DIR in shot["env"] and shot["env"][config.ENV_OUT_DIR].endswith("visual-fidelity-out/ci-fixture")
    for step in job["steps"]:
        run = str(step.get("run", ""))
        assert "curl" not in run and "wget" not in run, step
