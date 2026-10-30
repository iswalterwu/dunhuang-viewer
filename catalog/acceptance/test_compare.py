"""比较真实实现和真实合成导入报告；无服务、数据库或网络。"""

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from dh_catalog.importer import CatalogState, build_report, compute_import
from dh_catalog.v0 import IndexFetch
from uuid import uuid4

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("acceptance_compare", HERE / "compare.py")
comparator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparator)
# 复用真实影像生成夹具，acceptance 单独运行时也能找到；不改公共 conftest。
fixture_spec = importlib.util.spec_from_file_location("catalog_synthetic_fixtures", HERE.parent / "tests/conftest.py")
fixtures = importlib.util.module_from_spec(fixture_spec)
fixture_spec.loader.exec_module(fixtures)
roots = fixtures.roots
make_image = fixtures.make_image


@pytest.fixture
def baseline():
    return json.loads(comparator.BASELINE.read_text(encoding="utf-8"))


@pytest.fixture
def report(roots, make_image, tmp_path):
    directory = roots["data"] / "敦煌003/P.2504-1"
    make_image(directory / "native.tif")
    (directory / "说明.txt").write_text("合成附件", encoding="utf-8")
    cache = tmp_path / "cache"
    cache.mkdir()
    result = compute_import(roots, cache, run_id=1, attachment_sink=lambda file, raw: uuid4())
    return build_report(result, CatalogState(), IndexFetch(None, "合成：未连接 v0"))


def subset(baseline, *ids):
    selected = copy.deepcopy(baseline)
    selected["metrics"] = [metric for metric in selected["metrics"] if metric["id"] in ids]
    return selected


def by_id(result, key):
    return next(row for row in result["metrics"] if row["id"] == key)


def run_cli(tmp_path, document, baseline=None, notes=None):
    path = tmp_path / "中文证据 报告.json"
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    args = [sys.executable, "-I", "-X", "utf8", str(HERE / "compare.py"), str(path)]
    for option, value in (("baseline", baseline), ("notes", notes)):
        if value is not None:
            target = tmp_path / f"{option}.json"
            target.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
            args += [f"--{option}", str(target)]
    return subprocess.run(args, capture_output=True, encoding="utf-8", check=False)


@pytest.mark.parametrize("shape", ["cli", "api", "direct"])
def test_actual_build_report_wrappers(report, baseline, shape):
    document = {"status": "succeeded", "counts" if shape == "cli" else "report": report} if shape != "direct" else report
    result = comparator.compare(document, baseline)
    assert by_id(result, "data_tiff")["actual"] == 1
    assert by_id(result, "txt")["actual"] == 1
    assert by_id(result, "p2504_parts")["actual"] == 1
    assert by_id(result, "bnf_directories")["actual"] == 1
    assert by_id(result, "missing_manifest")["actual"] == 0
    assert result["shape"] == {"cli": "cli-row", "api": "api-row", "direct": "direct-report"}[shape]
    assert result["batch_status"] == (None if shape == "direct" else "succeeded")
    assert result["exit_code"] == 1
    assert result["summary"]["unverified"] == 3
    assert result["summary"]["missing"] == 0


def test_entire_baseline_is_registered(baseline):
    expected = {
        "image_directories": 6096, "data_tiff": 32058, "backup_tiff": 925, "psb": 16,
        "page_jpg": 2831, "preview_jpg": 68, "excluded_tile_jpg": 98, "txt": 477,
        "manifest": 5140, "report": 5140, "index": 66, "hidden_files": 42,
        "hidden_colocated": 10, "loose_files": 8, "multi_number_units": 7,
        "wb_units": 46, "wa_units": 1, "doubtful_pelliot_count": 2,
        "doubtful_pelliot_numbers": ["P.0901", "P.5257"], "suspected_numbers": 2,
        "outside_vocabulary": 1, "missing_manifest": 0, "missing_images": 0,
        "p2504_parts": 4, "p2504_resolve": 5, "merged_scrolls": 12,
        "merged_scrolls_accounted": 12, "kaibao_suggestions": 18, "title_clue_suggestions": 6,
        "p0901_items": 3, "bnf_directories": 447, "processed_directories": 499,
        "local_directories": 12, "nlc_directories": 5138,
    }
    assert baseline["date"] == "2026-10-27"
    assert {m["id"]: m["expected"] for m in baseline["metrics"]} == expected


def test_q024_explanation_never_erases_difference(report, baseline, tmp_path):
    report["counts"]["attachments_by_kind"]["text"] = 483
    selected = subset(baseline, "txt")
    note = {"txt": "Q-024 新 A077 资料六个 txt；须附实际附件证据"}
    result = run_cli(tmp_path, {"status": "succeeded", "report": report}, selected, note)
    assert result.returncode == 1
    row = json.loads(result.stdout)["metrics"][0]
    assert (row["expected"], row["actual"], row["delta"], row["result"]) == (477, 483, 6, "difference")
    assert row["explanation"] == note["txt"]


def test_q024_real_attachment_pipeline(roots, make_image, tmp_path, baseline):
    directory = roots["data"] / "敦煌003/P2002"
    make_image(directory / "native.tif")
    for i in range(477):
        (directory / f"合成旧附件{i}.txt").write_text("合成", encoding="utf-8")
    added = roots["data"] / "A077-敦煌文献目录/合成只有附件"
    added.mkdir(parents=True)
    for i in range(6):
        (added / f"新增{i}.txt").write_text("合成 Q-024", encoding="utf-8")
    cache = tmp_path / "cache"
    cache.mkdir()
    computation = compute_import(roots, cache, run_id=1, attachment_sink=lambda file, raw: uuid4())
    report = build_report(computation, CatalogState(), IndexFetch(None, "不连接 v0"))
    result = comparator.compare({"status": "succeeded", "counts": report}, baseline,
                                {"txt": "合成 Q-024 六个新增附件"})
    assert by_id(result, "txt")["delta"] == 6
    assert by_id(result, "txt")["actual"] == 483
    assert by_id(result, "missing_images")["actual"] == 1
    assert len(report["unassigned_attachments"]) == 6
    assert "A077-敦煌文献目录" in report["new_categories"]
    assert result["exit_code"] == 1


@pytest.mark.parametrize("shape", ["cli", "api"])
@pytest.mark.parametrize("status", ["running", "failed"])
def test_unsuccessful_batch_even_with_matching_counts(report, baseline, tmp_path, shape, status):
    result = run_cli(tmp_path, {"status": status, "counts" if shape == "cli" else "report": report},
                     subset(baseline, "missing_manifest"))
    assert result.returncode == 4
    assert json.loads(result.stdout)["batch_status"] == status


def test_empty_running_report_is_not_success(baseline):
    result = comparator.compare({"status": "running", "counts": {}}, baseline)
    assert result["exit_code"] == 4
    assert by_id(result, "data_tiff")["result"] == "missing"


@pytest.mark.parametrize("container, expected_result, actual", [({}, "match", 0), (None, "missing", None)])
def test_sparse_zero_requires_existing_container(report, baseline, container, expected_result, actual):
    if container is None:
        del report["counts"]["anomalies_by_category"]
    else:
        report["counts"]["anomalies_by_category"] = container
    result = comparator.compare({"status": "succeeded", "report": report}, subset(baseline, "missing_manifest"))
    row = result["metrics"][0]
    assert row["result"] == expected_result and row["actual"] == actual
    assert result["exit_code"] == (0 if container == {} else 2)


def test_true_zero_and_sparse_zero_distinguished(report, baseline):
    report["counts"]["anomalies_by_category"] = {"缺少清单": 0}
    result = comparator.compare({"status": "succeeded", "report": report}, subset(baseline, "missing_manifest"))
    assert result["metrics"][0]["sparse_zero"] is False
    del report["counts"]["anomalies_by_category"]["缺少清单"]
    result = comparator.compare({"status": "succeeded", "report": report}, subset(baseline, "missing_manifest"))
    assert result["metrics"][0]["sparse_zero"] is True


def test_missing_scalar_is_not_zero(report, baseline):
    del report["counts"]["data_tiff"]
    result = comparator.compare({"status": "succeeded", "report": report}, subset(baseline, "data_tiff"))
    assert result["metrics"][0]["actual"] is None
    assert result["exit_code"] == 2


def test_direct_report_matching_counts_still_lacks_status(report, baseline, tmp_path):
    result = run_cli(tmp_path, report, subset(baseline, "missing_manifest"))
    assert result.returncode == 2
    assert "直接报告不含批次成功状态" in result.stdout


def test_manual_proofs_not_fabricated_from_totals(report, baseline):
    report["counts"].update(excluded_jpg=98, outputs_with_derivation=12, merged_scrolls=12)
    result = comparator.compare({"status": "succeeded", "report": report},
                                subset(baseline, "excluded_tile_jpg", "p2504_resolve", "merged_scrolls_accounted"))
    assert result["exit_code"] == 2
    assert result["summary"]["unverified"] == 3
    assert all(row["actual"] is None and row["follow_up"] for row in result["metrics"])
    assert by_id(result, "excluded_tile_jpg")["observed"] == 98


@pytest.mark.parametrize("value", [None, True, -1, 1.5, "1", {}, [1]])
def test_invalid_scalar_counts_fail_without_traceback(report, baseline, tmp_path, value):
    report["counts"]["data_tiff"] = value
    result = run_cli(tmp_path, {"status": "succeeded", "report": report}, subset(baseline, "data_tiff"))
    assert result.returncode == 3
    assert "输入无效" in result.stderr and "Traceback" not in result.stderr


@pytest.mark.parametrize("value", [None, [], {"其他": True}, {"其他": -1}])
def test_invalid_sparse_container_does_not_hide_missing_key(report, baseline, value):
    report["counts"]["anomalies_by_category"] = value
    with pytest.raises(comparator.InputError):
        comparator.compare(report, subset(baseline, "missing_manifest"))


@pytest.mark.parametrize("document", [[], {"status": "done", "report": {}}, {"report": {}},
                                       {"counts": {"counts": {}}}, {"status": "succeeded", "report": None},
                                       {"counts": []}])
def test_invalid_shapes(document, baseline):
    with pytest.raises(comparator.InputError):
        comparator.compare(document, baseline)


@pytest.mark.parametrize("raw", [b'{"secret": "do-not-print",', b"\xff", b"<html>login</html>"])
def test_damaged_input_readable_error(tmp_path, raw):
    path = tmp_path / "损坏.json"
    path.write_bytes(raw)
    result = subprocess.run([sys.executable, "-I", "-X", "utf8", str(HERE / "compare.py"), str(path)],
                            capture_output=True, encoding="utf-8")
    assert result.returncode == 3
    assert "有效 UTF-8 JSON" in result.stderr
    assert "do-not-print" not in result.stderr and "Traceback" not in result.stderr


def test_missing_file(tmp_path):
    result = subprocess.run([sys.executable, "-I", "-X", "utf8", str(HERE / "compare.py"), str(tmp_path / "不存在.json")],
                            capture_output=True, encoding="utf-8")
    assert result.returncode == 3 and "报告不可读" in result.stderr


def test_notes_and_baseline_errors(baseline, report):
    for bad in ({}, {"date": "date", "scope": "scope", "metrics": []}):
        with pytest.raises(comparator.InputError):
            comparator.compare(report, bad)
    for notes in ({"not-a-metric": "x"}, {"txt": 1}, []):
        with pytest.raises(comparator.InputError):
            comparator.compare(report, baseline, notes)


def test_stdlib_cli_success_and_read_only(report, baseline, tmp_path):
    selected = subset(baseline, "missing_manifest")
    path = tmp_path / "中文报告.json"
    base = tmp_path / "基线.json"
    path.write_text(json.dumps({"status": "succeeded", "counts": report}), encoding="utf-8")
    base.write_text(json.dumps(selected), encoding="utf-8")
    before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in (path, base)}
    # -I -S 去掉第三方包、项目路径与 site；审计实际打开与 socket / 写操作。
    code = """
import runpy, sys
from pathlib import Path
script, report, baseline = sys.argv[1:]
namespace = runpy.run_path(script)
# argparse 延迟加载 locale/gettext；预热 --help 后才审计实际比较。
try:
    namespace['main'](['--help'])
except SystemExit:
    pass
def audit(event, args):
    if event in ('os.listdir', 'os.scandir') or event.startswith('socket.'):
        raise AssertionError(event)
    if event == 'open' and isinstance(args[0], str):
        mode = args[1]
        if mode and any(flag in mode for flag in 'wax+'):
            raise AssertionError('write')
        if any(part in args[0] for part in ('dh_catalog', 'users.json', '.env')):
            raise AssertionError('private input')
sys.addaudithook(audit)
raise SystemExit(namespace['main']([report, '--baseline', baseline]))
"""
    result = subprocess.run([sys.executable, "-I", "-S", "-B", "-X", "utf8", "-c", code,
                             str(HERE / "compare.py"), str(path), str(base)], capture_output=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout[result.stdout.index('{'):])["exit_code"] == 0
    assert before == {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in (path, base)}
    assert sorted(p.name for p in tmp_path.iterdir() if p.is_file()) == sorted(before)


def test_number_list_comparison_does_not_parse_names(report, baseline):
    report["counts"]["doubtful_pelliot_numbers"] = ["P.5257", "P.0901"]
    selected = subset(baseline, "doubtful_pelliot_numbers")
    result = comparator.compare({"status": "succeeded", "report": report}, selected)
    assert result["exit_code"] == 0
    report["counts"]["doubtful_pelliot_numbers"] = ["P5257", "P.0901"]
    result = comparator.compare({"status": "succeeded", "report": report}, selected)
    assert result["exit_code"] == 1
    assert result["metrics"][0]["delta"] == {"missing": ["P.5257"], "extra": ["P5257"]}


def test_acceptance_sources_utf8_lf():
    for name in ("baseline-2026-10-27.json", "compare.py", "test_compare.py"):
        raw = (HERE / name).read_bytes()
        raw.decode("utf-8")
        assert b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf")
