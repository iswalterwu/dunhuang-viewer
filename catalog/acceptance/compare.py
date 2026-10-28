"""只读保存的导入报告；标准库，无数据库、网络、原材料或业务规则依赖。"""

import argparse
import json
from pathlib import Path
import sys

BASELINE = Path(__file__).with_name("baseline-2026-10-27.json")
# build_report 的这些字段是 Counter 的 dict；仅容器有效时，未出现的键才表示零。
SPARSE_COUNTERS = {
    "attachments_by_kind", "anomalies_by_category", "parts_by_parent",
    "items_by_doubtful_number", "directories_by_lineage",
}


class InputError(ValueError):
    """可读且不包含原输入内容的边界错误。"""


def compare(document, baseline, notes=None):
    """返回 JSON 可序列化结果；match 只表示该统计相同，不代表 AC 通过。"""
    metrics = _validate_baseline(baseline)
    notes = _validate_notes(notes, metrics)
    shape, status, counts = _unwrap(document)
    rows = [_compare_metric(metric, counts, notes) for metric in metrics]
    summary = {name: sum(row["result"] == name for row in rows)
               for name in ("match", "difference", "missing", "unverified")}
    if status in {"running", "failed"}:
        code, conclusion = 4, "批次未成功，不能验收"
    elif summary["difference"]:
        code, conclusion = 1, "存在差异；解释不抹除差异，缺证据项仍须核查"
    elif status is None or summary["missing"] or summary["unverified"]:
        code, conclusion = 2, "缺少验收证据；不能宣称完成验收"
    else:
        code, conclusion = 0, "所选基线计数相同；不代表完整 AC 或 A1～A7 通过"
    return {
        "baseline_date": baseline["date"], "scope": baseline["scope"],
        "shape": shape, "batch_status": status,
        "batch_evidence": "批次成功" if status == "succeeded" else (
            "直接报告不含批次成功状态" if status is None else "批次未成功"),
        "metrics": rows, "summary": summary, "conclusion": conclusion, "exit_code": code,
    }


def _unwrap(document):
    if not isinstance(document, dict):
        raise InputError("报告顶层必须是 JSON 对象（不是导入列表或 HTML）")
    if "status" in document or "report" in document:
        status = document.get("status")
        if status not in ("running", "failed", "succeeded"):
            raise InputError("批次 status 缺失或无效")
        if "report" in document:
            shape, report = "api-row", document["report"]
        else:
            shape, report = "cli-row", document.get("counts")
    else:
        shape, status, report = "direct-report", None, document
    if not isinstance(report, dict):
        raise InputError("完整报告必须是 JSON 对象")
    # running/failed 的已保存报告可以为空；逐项输出缺证据，且退出码绝不为零。
    counts = report.get("counts", {})
    if not isinstance(counts, dict):
        raise InputError("报告 counts 必须是统计对象")
    # 不将 CLI 整行漏掉 status 后误当直接报告统计。
    if "counts" in counts:
        raise InputError("报告包裹层不正确：CLI 整行必须保留 status")
    return shape, status, counts


def _validate_baseline(baseline):
    if (not isinstance(baseline, dict) or not isinstance(baseline.get("date"), str)
            or not isinstance(baseline.get("scope"), str)
            or not isinstance(baseline.get("metrics"), list) or not baseline["metrics"]):
        raise InputError("基线须含 date、scope 与非空 metrics")
    ids = set()
    for metric in baseline["metrics"]:
        if not isinstance(metric, dict):
            raise InputError("基线指标必须是对象")
        key = metric.get("id")
        if not isinstance(key, str) or not key or key in ids:
            raise InputError("基线指标 id 缺失或重复")
        ids.add(key)
        if not isinstance(metric.get("label"), str) or "path" not in metric:
            raise InputError("基线指标须含 label 与 path")
        _check_value(metric.get("expected"))
        for field in ("path", "observed_path"):
            path = metric.get(field)
            if path is not None and (not isinstance(path, list) or not 1 <= len(path) <= 2
                                     or not all(isinstance(part, str) and part for part in path)):
                raise InputError("基线字段路径须是一个或两个非空字符串")
        if metric["path"] is None and not isinstance(metric.get("follow_up"), str):
            raise InputError("不可自动证明的指标必须提供后续核查入口")
    return baseline["metrics"]


def _validate_notes(notes, metrics):
    if notes is None:
        return {}
    if (not isinstance(notes, dict) or not all(isinstance(value, str) for value in notes.values())
            or not set(notes) <= {metric["id"] for metric in metrics}):
        raise InputError("差异说明必须为已知指标 id 到文字的 JSON 对象")
    return notes


def _check_value(value):
    if type(value) is int and value >= 0:
        return
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return
    raise InputError("指标必须是非负整数（不接受布尔或小数）或字符串列表")


def _count(counts, path):
    if path[0] not in counts:
        return None, False
    value = counts[path[0]]
    if len(path) == 2:
        if not isinstance(value, dict):
            raise InputError("嵌套统计容器类型错误")
        if path[0] in SPARSE_COUNTERS:
            if not all(type(number) is int and number >= 0 for number in value.values()):
                raise InputError("Counter 容器必须只包含非负整数")
            return value.get(path[1], 0), path[1] not in value
        if path[1] not in value:
            return None, False
        value = value[path[1]]
    _check_value(value)
    return value, False


def _compare_metric(metric, counts, notes):
    row = {key: metric[key] for key in ("id", "label", "expected")}
    row.update(actual=None, delta=None, result="unverified", source=metric["path"],
               explanation=notes.get(metric["id"], ""), follow_up=metric.get("follow_up", ""))
    if metric["path"] is None:
        row["reason"] = "既有计数不能直接证明；须按后续入口人工留证"
        if metric.get("observed_path"):
            value, _ = _count(counts, metric["observed_path"])
            row.update(observed=value, observed_source=metric["observed_path"])
        return row
    actual, sparse_zero = _count(counts, metric["path"])
    row["actual"] = actual
    row["sparse_zero"] = sparse_zero
    if actual is None:
        row.update(result="missing", reason="缺少计数或容器，未按零填充")
        return row
    expected = metric["expected"]
    if type(actual) is not type(expected):
        raise InputError("实际指标与基线指标类型不一致")
    if type(expected) is int:
        row["delta"] = actual - expected
        same = actual == expected
    else:
        # 号码列表只比较顺序无关的成员；不解析或规范化编号。
        same = sorted(actual) == sorted(expected)
        row["delta"] = {"missing": sorted(set(expected) - set(actual)),
                        "extra": sorted(set(actual) - set(expected))}
    row["result"] = "match" if same else "difference"
    return row


def _read_json(path, label):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, RecursionError):
        raise InputError(f"{label}不可读或不是有效 UTF-8 JSON") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", help="已保存的 CLI/API 单批次导出 JSON，或直接报告")
    parser.add_argument("--baseline", default=BASELINE, help="基线 JSON（默认随脚本的 2026-10-27 基线）")
    parser.add_argument("--notes", help="可选：指标 id 到差异原因的 JSON；不会改变比较结果")
    args = parser.parse_args(argv)
    try:
        result = compare(_read_json(args.report, "报告"), _read_json(args.baseline, "基线"),
                         _read_json(args.notes, "差异说明") if args.notes else None)
    except InputError as error:
        print(f"输入无效：{error}", file=sys.stderr)
        return 3
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
