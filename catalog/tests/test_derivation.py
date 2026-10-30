"""合成同形执行记录；真实文件 / scan / 审计事件，不访问 NAS。"""

import json
import os
import sys
from pathlib import Path, PurePosixPath

import pytest

from dh_catalog.derivation import CACHE_FILES, open_cache_record, resolve_derivations
from dh_catalog.scan import scan

DIRECTORY = "合成分类/样卷 甲"
FINAL = f"{DIRECTORY}/合并长卷.tif"
INTERMEDIATE = f"{DIRECTORY}/合并长卷_psb.tif"


@pytest.fixture
def cache(tmp_path):
    directory = tmp_path / "v0cache"
    directory.mkdir()
    plans = {
        "seg_move_plan.json": {"plan": [], "skipped": []},
        "samefolder_plan.json": {"has_merged": [], "sequence": [], "other": []},
        "validated_moves.json": {"moves": [], "manual": []},
    }
    for name in CACHE_FILES:
        (directory / name).write_text(json.dumps(plans[name]) if name in plans else "", encoding="utf-8")
    return directory


def write_log(cache, name, text):
    (cache / name).write_text(text, encoding="utf-8", newline="\n")


def stitch(directory=DIRECTORY, clock="08:00:00"):
    return (
        f"===== {clock} 开始: {directory}/分段 =====\n"
        "裁剪黑边(仅左右)拼接：2 片\n"
        "   1.tif x0= 0 w= 7\n"
        "   2.tif x0= 1 w= 6\n"
        f"完成: /data/{directory}/合并长卷.tif  13 x 5  0.01GB  用时 1.0s\n"
        "退出码: 0\n"
    )


def psb_conversion(clock="14:00:00", replacement=True):
    return (
        f"===== {clock} 转换: {DIRECTORY} =====\n"
        "PSB 14x5 ch=4 mode=4 depth=8\n"
        "raw 完成: /cache/synthetic.raw  0.01GB  1.0s\n"
        f"TIFF 写完成: /data/{INTERMEDIATE}  0.01GB  bigtiff=False\n"
        f"TIFF 完成: /data/{INTERMEDIATE}  0.01GB\n"
        "退出码: 0\n"
    ) + ("  已替换合并长卷.tif\n" if replacement else "")


def material(roots, make_image, *, source_root="backup", source_dir="分段"):
    make_image(roots["data"] / FINAL)
    for name in ("1.tif", "2.tif"):
        make_image(roots[source_root] / DIRECTORY / source_dir / name)
    return scan(roots).images


@pytest.mark.parametrize("log_name,source_root,source_dir", [
    ("merge_all.log", "backup", "分段"),
    ("merge_all.log", "data", "分段"),
    ("merge_smart_all.log", "backup", "分段"),
    ("merge_extra.log", "backup", ""),
])
def test_stitch_and_psb_logs(cache, roots, make_image, log_name, source_root, source_dir):
    images = material(roots, make_image, source_root=source_root, source_dir=source_dir)
    if log_name == "merge_all.log":
        text, completion_line = stitch(), 5
    else:
        text = (
            f"===== 09:00:00 开始: {DIRECTORY} =====\n"
            "分片 2 个，PSB 有\n"
            "  段1: PSB位置 x= 7  NCC=0.900\n"
            "  段2: PSB位置 x= 0  NCC=0.910\n"
            "检测顺序（段号）: [2, 1] | 平均NCC 0.905\n"
            f"完成: /data/{FINAL}  14 x 5  0.01GB  顺序=[2, 1]\n"
            "退出码: 0\n"
        )
        completion_line = 6
    write_log(cache, log_name, text)
    result = resolve_derivations(cache, images)
    assert len(result.edges) == 2
    assert {edge.source.root for edge in result.edges} == {source_root}
    assert {edge.source.relative_path.name for edge in result.edges} == {"1.tif", "2.tif"}
    assert all(edge.output.relative_path == PurePosixPath(FINAL) for edge in result.edges)
    assert all(edge.method == "拼接" and edge.evidence_file == log_name
               and edge.evidence_line == completion_line for edge in result.edges)
    assert result.outputs == frozenset({("data", PurePosixPath(FINAL))})
    assert not result.issues


def test_psb_replacement_overrides_old_stitch(cache, roots, make_image):
    material(roots, make_image)
    make_image(roots["data"] / DIRECTORY / "合成源.psb")
    write_log(cache, "merge_all.log", stitch())
    write_log(cache, "psb_convert_7.log", psb_conversion())
    result = resolve_derivations(cache, scan(roots).images)
    assert len(result.edges) == 1
    edge = result.edges[0]
    assert edge.method == "PSB 转换"
    assert edge.source.relative_path.name == "合成源.psb"
    assert edge.output.relative_path == PurePosixPath(FINAL)
    assert (edge.evidence_file, edge.evidence_line) == ("psb_convert_7.log", 7)
    assert not result.issues


def test_last_success_uses_record_time_not_whitelist_order_or_mtime(cache, roots, make_image):
    material(roots, make_image)
    make_image(roots["data"] / DIRECTORY / "合成源.psb")
    # 白名单中拼接日志更早，mtime 也更早，但其操作时间更晚。
    write_log(cache, "merge_all.log", stitch(clock="16:00:00"))
    os.utime(cache / "merge_all.log", (1, 1))
    write_log(cache, "psb_convert_7.log", psb_conversion(clock="14:00:00"))
    result = resolve_derivations(cache, scan(roots).images)
    assert len(result.edges) == 2
    assert {edge.method for edge in result.edges} == {"拼接"}


def test_failed_tail_does_not_discard_prior_success(cache, roots, make_image):
    images = material(roots, make_image)
    write_log(cache, "merge_smart_all.log", stitch() + (
        f"===== 09:00:00 开始: {DIRECTORY} =====\n"
        "分片 0 个，PSB 无\n"
        "Traceback (most recent call last):\n"
        "IndexError: synthetic failure\n"
        "退出码: 1\n"
        "===== 全部完成 09:00:01 =====\n"
    ))
    result = resolve_derivations(cache, images)
    assert len(result.edges) == 2
    assert all(edge.evidence_line == 5 for edge in result.edges)
    assert any("操作失败" in issue.reason for issue in result.issues)


@pytest.mark.parametrize("failure", [
    "raw 完成: /cache/synthetic.raw  0.01GB\n退出码: 0\n",
    "raw 完成: /cache/synthetic.raw  0.01GB\nTraceback (most recent call last):\n退出码: 0\n",
    f"TIFF 写完成: /data/{INTERMEDIATE}  0.01GB\n退出码: 0\n",
    f"TIFF 完成: /data/{INTERMEDIATE}  0.01GB\n退出码: 1\n已替换合并长卷.tif\n",
])
def test_raw_exit_zero_and_failed_conversion_are_not_success(cache, roots, make_image, failure):
    material(roots, make_image)
    make_image(roots["data"] / DIRECTORY / "合成源.psb")
    write_log(cache, "merge_all.log", stitch())
    write_log(cache, "psb_convert.log", "PSBNAME: 合成源.psb\n" + failure)
    result = resolve_derivations(cache, scan(roots).images)
    assert len(result.edges) == 2
    assert {edge.method for edge in result.edges} == {"拼接"}
    assert any(issue.evidence_file == "psb_convert.log" for issue in result.issues)


@pytest.mark.parametrize("header", [
    f"===== 12:00:00 转换: {DIRECTORY} / .合成源.psb =====\n",
    "PSBNAME: .合成源.psb\n",
])
def test_intermediate_tiff_is_not_final_replacement(cache, roots, make_image, header):
    make_image(roots["data"] / FINAL)
    make_image(roots["data"] / INTERMEDIATE)
    make_image(roots["data"] / DIRECTORY / ".合成源.psb")
    write_log(cache, "psb_conv_wb5back.log", header + (
        "raw 完成: /cache/synthetic.raw  0.01GB\n"
        f"TIFF 写完成: /data/{INTERMEDIATE}  0.01GB  bigtiff=True\n"
        f"TIFF 完成: /data/{INTERMEDIATE}  0.01GB\n"
        "退出码: 0\n"
    ))
    result = resolve_derivations(cache, scan(roots).images)
    assert len(result.edges) == 1
    assert result.edges[0].output.relative_path == PurePosixPath(INTERMEDIATE)
    assert result.edges[0].source.relative_path.name == ".合成源.psb"
    assert ("data", PurePosixPath(FINAL)) not in result.outputs
    assert any("没有替换" in issue.reason and issue.relative_path == PurePosixPath(FINAL)
               for issue in result.issues)


def test_missing_intermediate_is_not_mapped_to_final(cache, roots, make_image):
    make_image(roots["data"] / FINAL)
    make_image(roots["data"] / DIRECTORY / "合成源.psb")
    write_log(cache, "psb_convert_all.log", psb_conversion(replacement=False))
    result = resolve_derivations(cache, scan(roots).images)
    assert not result.edges and not result.outputs
    assert any("输出不在已扫描" in issue.reason for issue in result.issues)


def test_headerless_stitch_block_does_not_reuse_previous_directory(cache, roots, make_image):
    material(roots, make_image)
    second = "合成分类/样卷 乙"
    make_image(roots["data"] / second / "合并长卷.tif")
    for name in ("甲片.tif", "乙片.tif"):
        make_image(roots["backup"] / second / "分段" / name)
    write_log(cache, "merge_all.log", stitch() + (
        "裁剪黑边(仅左右)拼接：2 片\n"
        "甲片.tif x0= 0 w= 7\n乙片.tif x0= 0 w= 7\n"
        f"完成: /data/{second}/合并长卷.tif  14 x 5\n退出码: 0\n"
    ))
    result = resolve_derivations(cache, scan(roots).images)
    assert len(result.edges) == 4
    assert not result.issues
    assert {edge.source.relative_path.name for edge in result.edges
            if edge.output.relative_path.parent == PurePosixPath(second)} == {"甲片.tif", "乙片.tif"}


def test_successful_latest_with_unknown_source_never_falls_back(cache, roots, make_image):
    material(roots, make_image)
    make_image(roots["data"] / DIRECTORY / "候选甲.psb")
    make_image(roots["data"] / DIRECTORY / "候选乙.psb")
    write_log(cache, "merge_all.log", stitch())
    write_log(cache, "psb_convert_7.log", psb_conversion())
    result = resolve_derivations(cache, scan(roots).images)
    assert not result.edges
    assert ("data", PurePosixPath(FINAL)) in result.outputs
    assert any("PSB 源文件不能唯一确定" in issue.reason for issue in result.issues)


@pytest.mark.parametrize("problem", ["missing", "duplicate_roots", "extra_group", "no_count"])
def test_uncertain_fragment_sets_report_reason(cache, roots, make_image, problem):
    material(roots, make_image)
    text = stitch()
    if problem == "missing":
        (roots["backup"] / DIRECTORY / "分段/2.tif").unlink()
    elif problem == "duplicate_roots":
        make_image(roots["data"] / DIRECTORY / "分段/1.tif")
    else:
        text = (f"===== 09:00:00 开始: {DIRECTORY} =====\n"
                + ("分片 2 个，PSB 有\n" if problem == "extra_group" else "")
                + f"完成: /data/{FINAL}  14 x 5\n")
        if problem == "extra_group":
            for name in ("3.tif", "4.tif"):
                make_image(roots["backup"] / DIRECTORY / "切片" / name)
    write_log(cache, "merge_all.log", text)
    result = resolve_derivations(cache, scan(roots).images)
    assert not result.edges
    assert result.outputs
    assert any("分片" in issue.reason for issue in result.issues)


def test_missing_and_unreadable_whitelist_records_do_not_abort(cache, roots, make_image):
    images = material(roots, make_image)
    write_log(cache, "merge_all.log", stitch())
    (cache / "seg_move_log.txt").unlink()
    # 真实不可读对象，不 mock 权限（Windows 管理员下 chmod 不是可靠的读拒绝）。
    (cache / "extra_move_log.txt").unlink()
    (cache / "extra_move_log.txt").mkdir()
    (cache / "psb_convert.log").write_bytes(b"\xff\xfe\xff")
    result = resolve_derivations(cache, images)
    assert len(result.edges) == 2
    assert {issue.evidence_file for issue in result.issues} == {
        "seg_move_log.txt", "extra_move_log.txt", "psb_convert.log",
    }
    assert len(result.opened_paths) == 13
    assert all(issue.category == "派生来源不明" for issue in result.issues)


def test_unrecorded_output_and_move_plans_do_not_invent_derivations(cache, roots, make_image):
    images = material(roots, make_image)
    rel = f"{DIRECTORY}/分段"
    plans = {
        "seg_move_plan.json": {"plan": [{"src": f"/srv/legacy/images/{rel}",
            "dst": f"/srv/legacy/segments/{rel}", "rel": rel, "segment_count": 2}], "skipped": []},
        "samefolder_plan.json": {"has_merged": [{"rel": DIRECTORY,
            "merged": {"name": "合并长卷.tif", "w": 14}, "move": [{"name": "1.tif"}]}],
            "sequence": [], "other": []},
        "validated_moves.json": {"moves": [{"rel": DIRECTORY, "file": "1.tif",
            "src": f"/data/{DIRECTORY}/1.tif", "dst_dir": f"/backup/{DIRECTORY}",
            "keep": "合并长卷.tif"}], "manual": []},
    }
    for name, value in plans.items():
        write_log(cache, name, json.dumps(value, ensure_ascii=False))
    write_log(cache, "seg_move_log.txt", f"OK {rel}\n")
    write_log(cache, "samefolder_move_log.txt", "OK [1/1] 1.tif\n完成: 1 个，失败 0\n")
    write_log(cache, "extra_move_log.txt", "OK-DIR 分段\nOK-FILE 样卷/1.tif\n")
    result = resolve_derivations(cache, images)
    assert not result.edges and not result.outputs
    assert len(result.issues) == 1
    assert result.issues[0].relative_path == PurePosixPath(FINAL)
    assert "不在 2026-10-21 执行记录中" in result.issues[0].reason


@pytest.mark.parametrize("contents", ["[]", '{"plan": 3}', '{"plan":[{}]}', "{broken"])
def test_malformed_plan_reports_issue(cache, contents):
    write_log(cache, "seg_move_plan.json", contents)
    result = resolve_derivations(cache, [])
    assert len(result.issues) == 1
    assert result.issues[0].evidence_file == "seg_move_plan.json"
    assert "格式错误" in result.issues[0].reason


def test_unknown_cross_log_time_does_not_guess_by_file_order(cache, roots, make_image):
    images = material(roots, make_image)
    write_log(cache, "merge_all.log", stitch())
    write_log(cache, "merge_extra.log", stitch().split("\n", 1)[1])
    result = resolve_derivations(cache, images)
    assert not result.edges and result.outputs
    assert any("不能确定最后成功操作" in issue.reason for issue in result.issues)


def test_moved_output_resolves_only_at_backup_mirror(cache, roots, make_image):
    material(roots, make_image)
    target = roots["backup"] / FINAL
    target.parent.mkdir(parents=True, exist_ok=True)
    (roots["data"] / FINAL).rename(target)
    write_log(cache, "merge_all.log", stitch())
    result = resolve_derivations(cache, scan(roots).images)
    assert len(result.edges) == 2
    assert all(edge.output.root == "backup" for edge in result.edges)
    assert result.outputs == frozenset({("backup", PurePosixPath(FINAL))})


@pytest.mark.parametrize("record_roots", [None, {"data": "/srv/legacy/images/", "backup": "/srv/legacy/segments/"}])
def test_cache_access_is_exact_readonly_whitelist_without_directory_listing(cache, roots, make_image, record_roots):
    images = material(roots, make_image)
    text = stitch()
    if record_roots:
        text = text.replace(f"开始: {DIRECTORY}", f"开始: /srv/legacy/segments/{DIRECTORY}")
        text = text.replace("完成: /data/", "完成: /srv/legacy/images/")
    write_log(cache, "merge_all.log", text)
    write_log(cache, "psb_convert.log", (
        "PSBNAME: 合成源.psb\nraw 完成: /cache/private.raw  1GB\n"
        "rm -rf /data\n退出码: 0\n"
    ))
    write_log(cache, "users.json", '{"not": "for import"}')
    (cache / "seg_move_log.txt").unlink()  # 审计记录也必须包含打开失败的路径。
    events = []
    active = True

    def audit(event, args):
        if active and event in {"open", "os.listdir", "os.scandir", "os.system", "subprocess.Popen"}:
            events.append((event, args))

    sys.addaudithook(audit)
    try:
        result = resolve_derivations(cache, images, record_roots=record_roots)
    finally:
        active = False
    assert len(result.edges) == 2
    assert {event for event, _ in events} == {"open"}
    actual = [Path(args[0]) for _, args in events]
    names = (
        "merge_all.log merge_smart_all.log merge_extra.log psb_convert.log psb_convert_all.log "
        "psb_convert_7.log psb_conv_wb5back.log seg_move_log.txt samefolder_move_log.txt "
        "extra_move_log.txt seg_move_plan.json samefolder_plan.json validated_moves.json"
    ).split()
    expected = [cache.absolute() / name for name in names]
    assert actual == expected == result.opened_paths
    assert all(args[1] == "r" for _, args in events)
    assert all(path.name != "users.json" for path in actual)
    assert len(actual) == 13
    # 入口自身也限制名称；不得先尝试打开再判白名单。
    rejected = []
    with pytest.raises(ValueError, match="白名单"):
        open_cache_record(cache, "users.json", rejected)
    with pytest.raises(ValueError, match="白名单"):
        open_cache_record(cache, "../merge_all.log", rejected)
    assert not rejected


def test_log_paths_are_data_not_files_to_open(cache, roots, make_image):
    images = material(roots, make_image)
    write_log(cache, "merge_all.log", stitch().replace(f"/data/{FINAL}", "/etc/unknown.tif"))
    result = resolve_derivations(cache, images)
    assert not result.edges and not result.outputs
    assert any("不是 data / backup" in issue.reason for issue in result.issues)


@pytest.mark.parametrize("output_root", ["data", "backup"])
@pytest.mark.parametrize("style", ["container", "host"])
def test_record_prefixes_select_inventory_roots(cache, roots, make_image, output_root, style):
    material(roots, make_image)
    # Both locations exist, so an incorrect role cannot be hidden by backup fallback.
    make_image(roots["backup"] / FINAL)
    prefixes = ({"data": "/srv/legacy/images/", "backup": "/srv/legacy/segments/"}
                if style == "host" else {"data": "/data/", "backup": "/backup/"})
    text = stitch().replace(f"开始: {DIRECTORY}", f"开始: {prefixes['backup']}{DIRECTORY}")
    text = text.replace(f"/data/{FINAL}", prefixes[output_root] + FINAL)
    write_log(cache, "merge_all.log", text)
    kwargs = {"record_roots": prefixes} if style == "host" else {}
    result = resolve_derivations(cache, scan(roots).images, **kwargs)
    assert len(result.edges) == 2
    assert {edge.source.root for edge in result.edges} == {"backup"}
    assert {edge.source.relative_path.name for edge in result.edges} == {"1.tif", "2.tif"}
    assert all(edge.output.root == output_root and edge.output.relative_path == PurePosixPath(FINAL)
               and edge.method == "拼接" and edge.evidence_line == 5 for edge in result.edges)
    assert result.outputs == frozenset({(output_root, PurePosixPath(FINAL))})
    issue, = result.issues
    assert issue.root != output_root and issue.relative_path == PurePosixPath(FINAL)
    assert "无可确认的成功输出记录" in issue.reason


def test_relative_record_output_remains_supported(cache, roots, make_image):
    images = material(roots, make_image)
    write_log(cache, "merge_all.log", stitch().replace(f"/data/{FINAL}", FINAL))
    result = resolve_derivations(cache, images)
    assert len(result.edges) == 2 and not result.issues
    assert result.outputs == frozenset({("data", PurePosixPath(FINAL))})


@pytest.mark.parametrize("prefix", ["/srv/legacy/images/", "/srv/legacy/segments/", "/srv/legacy/images-other/"])
def test_unknown_absolute_record_prefix_is_explicit_issue(cache, roots, make_image, prefix):
    images = material(roots, make_image)
    write_log(cache, "merge_all.log", stitch().replace(f"/data/{FINAL}", prefix + FINAL))
    result = resolve_derivations(cache, images)
    assert not result.edges and not result.outputs
    assert any("不是 data / backup" in issue.reason and issue.evidence_file == "merge_all.log"
               for issue in result.issues)


@pytest.mark.parametrize("suffix", ["../outside.tif", "nested/../../outside.tif", "nested\\outside.tif"])
def test_configured_record_root_preserves_path_rejection(cache, roots, make_image, suffix):
    images = material(roots, make_image)
    write_log(cache, "merge_all.log", stitch().replace(f"/data/{FINAL}", "/srv/legacy/images/" + suffix))
    result = resolve_derivations(cache, images, record_roots={"data": "/srv/legacy/images/"})
    assert not result.edges and not result.outputs
    assert any("不是 data / backup" in issue.reason for issue in result.issues)


def test_configured_root_does_not_match_neighboring_directory(cache, roots, make_image):
    images = material(roots, make_image)
    write_log(cache, "merge_all.log", stitch().replace(f"/data/{FINAL}", "/srv/legacy/images-other/" + FINAL))
    result = resolve_derivations(cache, images, record_roots={"data": "/srv/legacy/images/"})
    assert not result.edges and not result.outputs
    assert any("不是 data / backup" in issue.reason for issue in result.issues)


def test_stitch_directory_mismatch_is_not_a_source_match(cache, roots, make_image):
    material(roots, make_image)
    other = "合成分类/别卷/合并长卷.tif"
    make_image(roots["data"] / other)
    write_log(cache, "merge_all.log", stitch().replace(f"/data/{FINAL}", f"/data/{other}"))
    result = resolve_derivations(cache, scan(roots).images)
    assert not result.edges
    assert any("拼接起始目录与输出位置不对应" in issue.reason for issue in result.issues)


def test_smart_stitch_uses_scanned_names_and_excludes_output(cache, roots, make_image):
    output = f"{DIRECTORY}/本地结果.tif"
    for name in ("图甲.tif", "图乙.tif", "本地结果.tif"):
        make_image(roots["data"] / DIRECTORY / name)
    write_log(cache, "merge_smart_all.log", (
        f"===== 10:00:00 开始: {DIRECTORY} =====\n"
        "分片 2 个，PSB 无\n检测顺序（段号）: [2, 1]\n"
        f"完成: /data/{output}  14 x 5\n退出码: 0\n"
    ))
    result = resolve_derivations(cache, scan(roots).images)
    assert {edge.source.relative_path.name for edge in result.edges} == {"图甲.tif", "图乙.tif"}
    assert result.outputs == frozenset({("data", PurePosixPath(output))})
    assert not result.issues


def test_failed_psb_tail_preserves_successful_replacement(cache, roots, make_image):
    make_image(roots["data"] / FINAL)
    make_image(roots["data"] / DIRECTORY / "合成源.psb")
    write_log(cache, "psb_convert_7.log", psb_conversion() + (
        f"===== 16:00:00 转换: {DIRECTORY} =====\n"
        "raw 完成: /cache/another.raw  0.01GB\n"
        "Traceback (most recent call last):\n退出码: 0\n"
    ))
    result = resolve_derivations(cache, scan(roots).images)
    assert len(result.edges) == 1
    assert result.edges[0].evidence_line == 7
    assert any("Traceback" in issue.reason for issue in result.issues)


def test_completely_missing_cache_does_not_abort(tmp_path, roots, make_image):
    make_image(roots["data"] / FINAL)
    result = resolve_derivations(tmp_path / "absent", scan(roots).images)
    assert not result.edges and not result.outputs
    assert len(result.opened_paths) == 13
    assert len(result.issues) == 14
    assert all(path.is_absolute() for path in result.opened_paths)


def test_last_success_in_same_log_and_explicit_psb_selection(cache, roots, make_image):
    make_image(roots["data"] / FINAL)
    for name in ("源甲.psb", "源乙.psb"):
        make_image(roots["data"] / DIRECTORY / name)
    first = psb_conversion(clock="13:00:00").replace(
        f"转换: {DIRECTORY} =====", f"转换: {DIRECTORY} / 源甲.psb =====",
    )
    second = psb_conversion(clock="14:00:00").replace(
        f"转换: {DIRECTORY} =====", f"转换: {DIRECTORY} / 源乙.psb =====\nPSBNAME: 源乙.psb",
    )
    write_log(cache, "psb_convert_all.log", first + second)
    result = resolve_derivations(cache, scan(roots).images)
    assert len(result.edges) == 1
    assert result.edges[0].source.relative_path.name == "源乙.psb"
    assert result.edges[0].evidence_line == 15
    assert not result.issues
