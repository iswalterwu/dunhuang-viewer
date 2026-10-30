"""一次导入的编排与持久化；不读取认证文件，不签发 cookie。

prepare_import 先取得连接和会话锁、提交 running 批次，再把生命周期交给
PreparedImport.execute（可在 HTTP 后台线程调用）。未派发成功应调用 cancel。
compute_import 是真实的扫描到预备写入阶段；attachment_sink 在每次读取后立即
消费原文，返回附件 UUID，不把全量 JSON 字节留在计算结果里。
"""

from collections import Counter, defaultdict
from collections.abc import Callable, Mapping
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
import json
from pathlib import Path, PurePosixPath
from uuid import UUID, uuid4

import httpx
from psycopg import Connection, sql
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from . import rules
from ._compact import CompactMap, ShapePool
from .db import import_lock
from .derivation import DerivationResult, resolve_derivations
from .identifiers import Identifier
from .identity import (
    ImageResolution, ImageState, ItemResolution, ItemState, SourcedIdentifier,
    resolve_images, resolve_items,
)
from .nlc import NlcResult, parse_nlc
from .scan import Fact, FileEntry, Inventory, ReadResult, read_facts, scan
from .units import UnitsResult, _merge_suggestions, build_units
from .v0 import HealthMonitor, IndexFetch, IndexSnapshot, V0Client, V0Volume


@dataclass(slots=True)
class CatalogState:
    """正式表的导入前状态；不包含附件原文。"""

    images: dict[UUID, Mapping] = field(default_factory=dict)
    items: dict[UUID, dict] = field(default_factory=dict)
    identifiers: dict[UUID, list[dict]] = field(default_factory=dict)
    links: dict[tuple[UUID, UUID], dict] = field(default_factory=dict)
    derivations: dict[tuple[UUID, UUID], dict] = field(default_factory=dict)
    attachments: dict[UUID, set[UUID]] = field(default_factory=dict)


@dataclass(slots=True)
class ImportComputation:
    inventory: Inventory
    units: UnitsResult
    image_resolution: ImageResolution
    item_resolution: ItemResolution
    readings: dict[FileEntry, ReadResult]
    nlc: dict[str, NlcResult]
    derivation: DerivationResult
    images: dict[UUID, Mapping]
    items: dict[UUID, dict]
    identifiers: dict[UUID, list[dict]]
    links: dict[tuple[UUID, UUID], dict]
    derivations: dict[tuple[UUID, UUID], dict]
    attachments: dict[FileEntry, UUID]
    item_attachments: dict[UUID, set[UUID]]
    anomalies: list[dict]


class PreparedImport:
    """拥有一个已持锁的连接；execute / cancel 均最终归还连接并释放会话。"""

    def __init__(self, connection, stack, run_id, client):
        self.connection = connection
        self.run_id = run_id
        self._stack = stack
        self._client = client
        self._finished = False

    def execute(
        self, roots: Mapping[str, Path], cache_dir: Path, *, record_roots: Mapping[str, str] | None = None,
    ) -> dict:
        if self._finished:
            raise RuntimeError("批次已结束")
        monitor = None
        result = None
        try:
            fetch = self._client.fetch_index()
            _save_snapshot(self.connection, self.run_id, fetch)
            with HealthMonitor(self._client) as monitor:
                with self.connection.transaction():
                    previous = load_catalog_state(self.connection)
                    result = compute_import(
                        roots, cache_dir, run_id=self.run_id, previous=previous, record_roots=record_roots,
                        attachment_sink=lambda file, raw: _save_attachment(self.connection, self.run_id, file, raw),
                    )
                    persist_import(self.connection, self.run_id, previous, result)
                    report = build_report(result, previous, fetch, latest_valid_snapshot(self.connection))
                    _save_report_details(self.connection, self.run_id, result, report)
            report["health"] = dict(_json_value(monitor.summary()), samples=_json_value(monitor.samples))
            _finish_run(self.connection, self.run_id, "succeeded", report)
            return report
        except BaseException as error:
            report = {
                "health": dict(_json_value(monitor.summary()), samples=_json_value(monitor.samples)) if monitor else {},
                "cache_access": [str(path) for path in result.derivation.opened_paths] if result else [],
            }
            # 不保存异常消息：驱动 / HTTP 异常可能带连接串、请求头等凭证。
            _finish_run(self.connection, self.run_id, "failed", report, type(error).__name__)
            raise
        finally:
            self._finished = True
            self._stack.close()
            self._client = None

    def cancel(self) -> None:
        """调用方不能派发后台执行时清理；不是导入运行中的暂停 / 中止机制。"""
        if not self._finished:
            try:
                _finish_run(self.connection, self.run_id, "failed", {}, "未派发执行")
            finally:
                self._finished = True
                self._stack.close()
                self._client = None


def prepare_import(
    pool: ConnectionPool, *, triggered_by: str, code_version: str, session_cookie: str,
    v0_url: str, http_client: httpx.Client | None = None,
) -> PreparedImport:
    """同步抢锁；ImportBusy 原样交给 API 转为 409。成功返回前不归还连接。

    认证及管理员校验属于调用方 HTTP 边界。http_client 仅用于 HTTP 边界注入。
    调用方必须 execute 或在后台派发失败时 cancel，不可遗弃返回的对象。
    """
    with ExitStack() as stack:
        connection = stack.enter_context(pool.connection())
        stack.enter_context(import_lock(connection))
        client = stack.enter_context(V0Client(v0_url, session_cookie, http_client))
        run_id = connection.execute("""
            INSERT INTO import_run(status, triggered_by, rule_version, code_version)
            VALUES ('running', %s, %s, %s) RETURNING id
        """, (triggered_by, rules.RULE_VERSION, code_version)).fetchone()["id"]
        return PreparedImport(connection, stack.pop_all(), run_id, client)


def _save_snapshot(connection, run_id, fetch):
    with connection.transaction():
        connection.execute("""
            UPDATE import_run SET v0_snapshot_status = %s, v0_snapshot_error = %s WHERE id = %s
        """, ("valid" if fetch.snapshot is not None else "unavailable", fetch.error, run_id))
        if fetch.snapshot is not None:
            for volume in fetch.snapshot.volumes.values():
                connection.execute("INSERT INTO v0_volume VALUES (%s, %s, %s)",
                                   (run_id, volume.id, str(volume.directory)))


def latest_valid_snapshot(connection: Connection) -> IndexSnapshot | None:
    """按有效批次选取，不能按非空 v0_volume 选取；失败导入的有效快照也有效。"""
    run = connection.execute("""
        SELECT id, started_at FROM import_run WHERE v0_snapshot_status = 'valid' ORDER BY id DESC LIMIT 1
    """).fetchone()
    if run is None:
        return None
    volumes = {}
    for row in connection.execute("SELECT * FROM v0_volume WHERE run_id = %s", (run["id"],)):
        path = PurePosixPath(row["relative_directory"])
        volumes[path] = V0Volume(row["volume_id"], path)
    return IndexSnapshot(run["started_at"], volumes)


def load_catalog_state(connection: Connection) -> CatalogState:
    state = CatalogState()
    basis = _BasisPool()
    # 已有正式事务时只建立保存点；autocommit 直调时结束短读事务。
    with connection.transaction():
        with _state_cursor(connection, "SELECT * FROM image") as cursor:
            state.images = {row["id"]: basis.compact_image(basis.share_row(row)) for row in cursor}
        with _state_cursor(connection, "SELECT * FROM item") as cursor:
            state.items = {row["id"]: basis.share_row(row) for row in cursor}
        with _state_cursor(connection, "SELECT * FROM identifier WHERE state IN ('current', 'pending') ORDER BY id") as cursor:
            for row in cursor:
                state.identifiers.setdefault(row["item_id"], []).append(basis.share_row(row))
        with _state_cursor(connection, "SELECT * FROM item_image") as cursor:
            state.links = {(row["item_id"], row["image_id"]): basis.share_row(row) for row in cursor}
        with _state_cursor(connection, "SELECT * FROM derivation") as cursor:
            state.derivations = {(row["image_id"], row["source_image_id"]): basis.share_row(row) for row in cursor}
        with _state_cursor(connection, "SELECT * FROM item_attachment") as cursor:
            for row in cursor:
                state.attachments.setdefault(row["item_id"], set()).add(row["attachment_id"])
    return state


@contextmanager
def _state_cursor(connection, query):
    # 消费者退出时立即关闭，不把关闭留给持有行生成器的 traceback / GC。
    with connection.cursor(name="catalog_state", scrollable=False, withhold=False) as cursor:
        cursor.itersize = 128
        cursor.execute(query)
        yield cursor


def compute_import(
    roots: Mapping[str, Path], cache_dir: Path, *, run_id: int,
    attachment_sink: Callable[[FileEntry, bytes], UUID], previous: CatalogState | None = None,
    at: datetime | None = None, record_roots: Mapping[str, str] | None = None,
) -> ImportComputation:
    """扫描 → 文件头 → 逐单元附件 / NLC → 派生 → 身份 → 规则 / 预备行。

    附件读取失败抛出 OSError，使正式事务回滚，绝不存空字节冒充原文。
    非数据库测试可消费 attachment_sink 验证读取顺序，不能拿它模拟数据库。
    """
    prior = CatalogState() if previous is None else previous
    now = datetime.now(UTC) if at is None else at
    inventory = scan(roots)
    units = build_units(inventory)
    readings = _read_images(inventory, roots, prior)
    attachments, nlc = _read_attachments(units, roots, attachment_sink)
    units.suggestions = _merge_suggestions(units.units)
    derivation = resolve_derivations(cache_dir, inventory.images, record_roots=record_roots)
    images = resolve_images([_image_state(row) for row in prior.images.values()], inventory.images, run_id, now)
    items = resolve_items(_item_states(prior), units.units, images.images)
    basis = _BasisPool(run_id, now)
    image_rows, link_rows, edge_rows = _image_rows(images, items, units, readings, nlc, derivation, prior, run_id, now, basis)
    item_rows, identifiers, item_attachments = _item_rows(items, units, nlc, image_rows, attachments, prior, run_id, now, basis)
    result = ImportComputation(
        inventory, units, images, items, readings, nlc, derivation, image_rows, item_rows,
        identifiers, link_rows, edge_rows, attachments, item_attachments, [],
    )
    result.anomalies = _collect_anomalies(result)
    return result


def _file_entry(row):
    return FileEntry(row["root"], PurePosixPath(row["relative_path"]), row["kind"],
                     row["size"], row["mtime_ns"], row["inode"])


def _image_state(row):
    return ImageState(row["id"], _file_entry(row), row["first_seen"], row["last_seen"], row["missing_since"])


def _item_states(prior):
    image_ids = defaultdict(set)
    for owner, image in prior.links:
        image_ids[owner].add(image)
    return [ItemState(
        row["id"], row["serial"], row["grouping_key"], frozenset(image_ids[row["id"]]), row["parent_id"],
        tuple(SourcedIdentifier(
            Identifier(i["system"], i["raw"], i["normalized"], row["grouping_key"] if i["compliant"] else None,
                       i["parent_number"], i["part"]),
            i["field_basis"]["raw"]["unit_key"],
        ) for i in prior.identifiers.get(row["id"], []) if i["state"] == "current"), tuple(row["clues"]),
    ) for row in prior.items.values()]


def _read_images(inventory, roots, prior):
    old = {_file_entry(row): row for row in prior.images.values() if row["read_ok"]}
    readings = {}
    for file in inventory.images:
        row = old.get(file)
        reading = None
        if row is not None:
            reading = ReadResult(file, {name: Fact(value["status"],
                tuple(value["value"]) if isinstance(value["value"], list) else value["value"])
                for name, value in row["facts"].items()})
        readings[file] = read_facts(file, roots[file.root], reading)
    return readings


def _read_attachments(units, roots, sink):
    attachments, nlc = {}, {}
    for unit in units.units:
        raw_nlc = {}
        for file in unit.attachments:
            raw = (roots[file.root] / file.relative_path).read_bytes()
            attachments[file] = sink(file, raw)
            if file.relative_path.parent == unit.relative_path and file.kind in {"manifest", "report"}:
                raw_nlc[file.kind] = raw
            del raw
        # 国图卷仅指分类下一级写卷目录，不含词表外子单元或散放文件。
        if (unit.relative_path.parts[0] == rules.NLC_CATEGORY and len(unit.relative_path.parts) == 2
                and all(member.file.relative_path != unit.relative_path for member in unit.images)):
            result = parse_nlc(unit, raw_nlc.get("manifest"), raw_nlc.get("report"))
            unit.parsed = result.parsed
            nlc[unit.key] = result
        # 不让上一单元的 manifest / report 留到下一单元。
        raw_nlc.clear()
    for file in units.unassigned_attachments:
        raw = (roots[file.root] / file.relative_path).read_bytes()
        attachments[file] = sink(file, raw)
        del raw
    return attachments, nlc


def _rule(name, source="默认规则", confidence="推断"):
    return asdict(rules._basis(name, source, confidence))


class _BasisPool:
    """一次计算或 DB 加载内复用 JSON 叶与影像形状；不共享可写字段映射。

    叶及其内嵌列表按只读消费，修改须替换字段引用。缓存有界，结束后释放；
    键为完整 JSON（含版本、run/at、位置及来源列表），不省略任何语义。
    """

    def __init__(self, run=None, at=None):
        self.run = run
        self.at = at.isoformat() if at is not None else None
        self.shapes = ShapePool()
        # 不用全局 intern：旧库可含任意历史作者/位置，不能永久保留。
        text = self.text = lru_cache(maxsize=512)(lambda value: value)

        @lru_cache(maxsize=4096)
        def leaf(encoded):
            return {text(key): text(value) if isinstance(value, str) else value
                    for key, value in json.loads(encoded).items()}

        self._leaf = leaf

    def share(self, value):
        return self._leaf(json.dumps(value, ensure_ascii=False, sort_keys=True))

    def share_fields(self, values):
        return {self.text(name): self.share(value) for name, value in values.items()}

    def share_row(self, row):
        # 在游标逐行反序列化后立即处理，不能先积累全表重复 JSON。
        row["field_basis"] = {
            self.text(name): self.share_fields(value) if name == "facts" else self.share(value)
            for name, value in row["field_basis"].items()
        }
        if "facts" in row:
            row["facts"] = self.share_fields(row["facts"])
        # 只复用不可变文本；行、字段映射、业务列表仍各自独立。
        for name, value in row.items():
            if isinstance(value, str):
                row[name] = self.text(value)
        return row

    def compact_image(self, row):
        # 仅压紧影像的四类外层；builder 写完后调用，叶和 JSON list 原样沿用。
        row["facts"] = self.shapes.compact(row["facts"])
        fields = row["field_basis"]
        if not isinstance(fields, CompactMap) and "facts" in fields:
            fields["facts"] = self.shapes.compact(fields["facts"])
        row["field_basis"] = self.shapes.compact(fields)
        return self.shapes.compact(row)


def _basis(values, semantic, old, pool):
    """值与语义依据都相同则沿用旧 run/time；批次本身不是变化。"""
    result = {}
    old_basis = old.get("field_basis", {})
    for name, meaning in semantic.items():
        previous = old_basis.get(name, {})
        old_meaning = {key: value for key, value in previous.items() if key not in {"run", "at"}}
        if _json_value(values[name]) == _json_value(old.get(name)) and meaning == old_meaning:
            result[name] = previous
        else:
            result[name] = pool.share(dict(meaning, run=pool.run, at=pool.at))
    return result


@dataclass(slots=True, weakref_slot=True)
class _ImagePolicyResolver:
    """本批源先于输出解析；memo 不捕获解析器，不依赖循环 GC 释放。"""

    by_file: dict
    unit_by_file: dict
    lineages: dict
    sources: dict
    pelliot_images: set
    nlc: dict
    policies: dict = field(default_factory=dict)

    def __call__(self, file):
        if file not in self.policies:
            unit = self.unit_by_file[file]
            self.policies[file] = rules.source_policy(
                file, self.lineages[file].value,
                has_pelliot=self.by_file[file].id in self.pelliot_images,
                attribution=self.nlc[unit.key].attribution if unit.key in self.nlc else None,
                sources=[self(source) for source in self.sources[file]],
            )
        return self.policies[file]


def _image_rows(images, items, units, readings, nlc, derivation, prior, run, at, basis):
    by_file = {image.file: image for image in images.images if image.missing_since is None}
    unit_by_file = {image.file: unit for unit in units.units for image in unit.images}
    lineages = {file: rules.detect_lineage(reading, derivation.outputs) for file, reading in readings.items()}
    sources = defaultdict(list)
    for edge in derivation.edges:
        sources[edge.output].append(edge.source)
    pelliot_images = {image_id for item in items.items
                      if item.grouping_key is not None and item.grouping_key.startswith("pelliot:")
                      for image_id in item.image_ids}
    # 只传本批次的源；实例不保存自身的 bound method。
    policy = _ImagePolicyResolver(by_file, unit_by_file, lineages, sources, pelliot_images, nlc)

    rows, links, edges = {}, dict(prior.links), dict(prior.derivations)
    item_images = {item.id: item.image_ids for item in items.items}
    for image in images.images:
        old = prior.images.get(image.id, {})
        file = image.file
        if image.missing_since is not None:
            row = dict(old, state="missing", missing_since=image.missing_since)
            row["field_basis"] = dict(old["field_basis"], **_basis(
                row, {"state": _rule("image-presence", "文件头", "确定"),
                      "missing_since": _rule("image-presence", "文件头", "确定")}, old, basis))
            rows[image.id] = basis.compact_image(row)
            continue
        reading, lineage, source = readings[file], lineages[file], policy(file)
        unit = unit_by_file[file]
        canvas = nlc[unit.key].canvases.get(file.relative_path) if unit.key in nlc else None
        row = dict(
            id=image.id, root=file.root, relative_path=str(file.relative_path),
            original_name=old.get("original_name", file.relative_path.name),
            original_path=old.get("original_path", str(file.relative_path)), hidden=file.hidden, kind=file.kind,
            size=file.size, mtime_ns=file.mtime_ns, inode=file.inode, read_ok=reading.error is None,
            read_error=reading.error,
            facts=basis.share_fields(_json_value(reading.facts)), lineage=lineage.value,
            collection=source.collection, acquisition=source.acquisition, license=source.license,
            attribution=source.attribution, display_policy=source.display, external_policy=source.external,
            canvas_number=canvas.number if canvas else None, canvas_id=canvas.id if canvas else None,
            state="present", first_seen=image.first_seen, last_seen=image.last_seen, missing_since=None,
        )
        semantic = {name: _rule("file-facts", "文件头", "确定") for name in row
                    if name not in {"id", "first_seen", "last_seen", "facts"}}
        semantic["lineage"] = asdict(lineage.basis)
        for name, rule_basis in source.basis.items():
            column = {"display": "display_policy", "external": "external_policy"}.get(name, name)
            semantic[column] = asdict(rule_basis)
            if lineage.value == "本地合成":
                semantic[column]["source_images"] = sorted(str(by_file[source_file].id) for source_file in sources[file])
        for name in ("root", "relative_path", "original_name", "original_path", "hidden", "kind"):
            semantic[name] = _rule("file-position", "文件名解析", "确定")
        for name in ("canvas_number", "canvas_id"):
            semantic[name] = (dict(_rule("nlc-canvas", "外部清单", "确定"),
                                   location=f"{unit.key}/manifest.json;report.json")
                              if unit.key in nlc else _rule("canvas-not-applicable"))
        semantic["state"] = _rule("image-presence", "文件头", "确定")
        semantic["missing_since"] = _rule("image-presence", "文件头", "确定")
        row["field_basis"] = _basis(row, semantic, old, basis)
        # 七个事实各有依据，不把整个 facts 的变化扩散为全部字段变化。
        fact_basis = _basis(row["facts"], {name: _rule("file-header", "文件头", "确定") for name in row["facts"]},
                            dict(old.get("facts", {}), field_basis=old.get("field_basis", {}).get("facts", {})), basis)
        row["field_basis"]["facts"] = fact_basis
        rows[image.id] = basis.compact_image(row)
    for unit in units.units:
        for member in unit.images:
            image = by_file[member.file]
            for owner in items.unit_items[unit.key]:
                # unit_items 包含本单元所有关联者；已有影像不能因此被额外关联到别件。
                if image.id not in item_images[owner]:
                    continue
                key = owner, image.id
                values = dict(item_id=owner, image_id=image.id, role=member.role,
                              source_directory=str(member.file.relative_path.parent), unit_key=unit.key)
                values["field_basis"] = _basis(values, {
                    "item_id": _rule("item-identity"), "image_id": _rule("image-identity"),
                    "role": _rule("image-role", "文件名解析"),
                    "source_directory": _rule("image-location", "文件名解析", "确定"),
                    "unit_key": _rule("unit-membership", "文件名解析"),
                }, prior.links.get(key, {}), basis)
                links[key] = values
    # 本批次在场的输出重算派生边，缺失输出保留原关系。
    present_ids = {image.id for image in by_file.values()}
    edges = {key: value for key, value in edges.items() if key[0] not in present_ids}
    for edge in derivation.edges:
        key = by_file[edge.output].id, by_file[edge.source].id
        values = dict(image_id=key[0], source_image_id=key[1], method=edge.method,
                      evidence_file=edge.evidence_file, evidence_line=edge.evidence_line)
        meaning = dict(_rule("derivation", "执行记录", "确定"),
                       location=f"{edge.evidence_file}:{edge.evidence_line}")
        values["field_basis"] = _basis(values, {name: meaning for name in values}, prior.derivations.get(key, {}), basis)
        edges[key] = values
    return rows, links, edges


def _provenance(value):
    return rules.Provenance(value["status"], tuple(value["evidence"]), value["judge"],
                            datetime.fromisoformat(value["at"]), value["suggestion"],
                            tuple(value["suggestion_evidence"]), value["evidence_conflict"])


def _item_rows(items, units, nlc, images, attachments, prior, run, at, basis):
    unit_map = {unit.key: unit for unit in units.units}
    by_owner = defaultdict(list)
    for key, owners in items.unit_items.items():
        for owner in owners:
            by_owner[owner].append(unit_map[key])
    rows, identifiers, item_attachments = {}, {}, {}
    for item in items.items:
        old = prior.items.get(item.id, {})
        own_units = by_owner[item.id]
        positions = list(old.get("original_positions", []))
        for unit in own_units:
            position = {"root": unit.root, "relative_path": str(unit.relative_path), "name": unit.name}
            if position not in positions:
                positions.append(position)
        policies = [rules.SourcePolicy(*(images[i][name] for name in (
            "collection", "acquisition", "license", "attribution", "display_policy", "external_policy")), {})
            for i in item.image_ids]
        item_attachments[item.id] = {attachments[file] for unit in own_units for file in unit.attachments}
        if item.id in items.preserved_items:
            # B 只冻结编号、线索、出处及依据；D 仍可为此写卷关联新单元。
            row = dict(old)
            identifiers[item.id] = prior.identifiers.get(item.id, [])
            item_attachments[item.id].update(prior.attachments.get(item.id, set()))
        else:
            provenance = rules.initial_provenance(item.grouping_key, own_units,
                _provenance(old["provenance"]) if old else None, at)
            row = dict(id=item.id, serial=item.serial, grouping_key=item.grouping_key,
                       provenance=_json_value(provenance), clues=list(item.clues),
                       created_run=old.get("created_run", run), updated_run=old.get("updated_run", run))
            semantic = {name: _rule("item-identity", "文件名解析") for name in (
                "grouping_key", "clues")}
            semantic["grouping_key"] = dict(_rule("item-identity"),
                identifier_sources=sorted({f"{unit.key}/manifest.json" if unit.key in nlc else unit.key
                                           for unit in own_units if item.grouping_key in unit.parsed.keys}))
            semantic["provenance"] = {"source": "人工" if provenance.judge.startswith("user:") else "默认规则",
                                      "author": provenance.judge,
                                      "confidence": "确定" if provenance.judge.startswith("user:") else "推断"}
            row["field_basis"] = _basis(row, semantic, old, basis)
            identifiers[item.id] = _identifier_rows(item, items, unit_map, nlc, prior, run, at, basis)
        row.update(parent_id=item.parent_id, original_positions=positions,
                   display_policy=rules.item_display_policy(policies))
        row["field_basis"] = dict(row["field_basis"], **_basis(row, {
            "parent_id": _rule("item-parent", "文件名解析"),
            "original_positions": _rule("original-positions", "文件名解析", "确定"),
            "display_policy": _rule("item-display-policy"),
        }, old, basis))
        if _changed(row, old, {"updated_run"}):
            row["updated_run"] = run
        rows[item.id] = row
    return rows, identifiers, item_attachments


def _identifier_rows(item, resolution, unit_map, nlc, prior, run, at, basis):
    old_rows = prior.identifiers.get(item.id, [])
    candidates = [(s, "current") for s in item.identifiers]
    candidates += [(s, "pending") for s in resolution.pending_identifiers.get(item.id, ())]
    desired = []
    for sourced, state in candidates:
        ident, key = sourced.value, sourced.unit_key
        unit = unit_map.get(key)
        origins = []
        if key in nlc:
            origins = [origin for value, origin in zip(nlc[key].parsed.identifiers, nlc[key].identifier_origins)
                       if value == ident]
        if origins:
            locations = [(origin.source, f"{origin.root}:{origin.relative_path}", origin.field) for origin in origins]
        elif unit is not None:
            locations = [("文件名解析", key, "name")]
        else:
            locations = [(i["source"], i["source_path"], i["field_basis"]["raw"].get("location_field", "name"))
                         for i in old_rows if i["raw"] == ident.raw and i["normalized"] == ident.normalized
                         and i["state"] == "current"]
        for source, path, location_field in locations:
            values = dict(item_id=item.id, system=ident.system, raw=ident.raw, normalized=ident.normalized,
                          parent_number=ident.parent, part=ident.part, source=source, source_path=path,
                          is_primary=False, compliant=ident.compliant, state=state)
            meaning = dict(_rule("identifier", source, "确定" if source == "外部清单" else "推断"),
                           unit_key=key, location_field=location_field)
            if not any(row[0] == values for row in desired):
                desired.append((values, meaning))
    primaries = [pair for pair in desired if pair[0]["state"] == "current" and pair[0]["compliant"]]
    if primaries:
        min(primaries, key=lambda pair: (pair[0]["source"] != "外部清单", pair[0]["source_path"]))[0]["is_primary"] = True
    result = []
    for values, meaning in desired:
        old = next((row for row in old_rows if all(row[name] == value for name, value in values.items())), {})
        semantic = {name: meaning for name in values if name != "item_id"}
        for name in ("raw", "source", "source_path"):
            semantic[name] = dict(meaning, confidence="确定")
        values["field_basis"] = _basis(values, semantic, old, basis)
        if old and values["field_basis"] == old["field_basis"]:
            result.append(old)
        elif old:
            result.append(dict(old, field_basis=values["field_basis"]))
        else:
            result.append(dict(values, since_run=run, until_run=None))
    return result


def _save_attachment(connection, run, file, raw):
    row = connection.execute("""
        INSERT INTO attachment(id, root, relative_path, kind, raw, encoding, created_run, updated_run)
        VALUES (%s, %s, %s, %s, %s, NULL, %s, %s)
        ON CONFLICT (root, relative_path) DO UPDATE SET
            raw = EXCLUDED.raw, kind = EXCLUDED.kind,
            updated_run = CASE WHEN attachment.raw IS DISTINCT FROM EXCLUDED.raw
                               THEN EXCLUDED.updated_run ELSE attachment.updated_run END
        RETURNING id
    """, (uuid4(), file.root, str(file.relative_path), file.kind, raw, run, run)).fetchone()
    return row["id"]


def persist_import(connection: Connection, run_id: int, previous: CatalogState, result: ImportComputation) -> None:
    """调用方必须包在正式事务内；互换先释放唯一值，再写最终值。"""
    _release_unique_values(connection, previous, result)
    for row in result.items.values():
        _upsert(connection, "item", row, ("id",))
    for row in result.images.values():
        _upsert(connection, "image", row, ("id",))
    _persist_identifiers(connection, run_id, previous, result)
    _persist_relations(connection, result)
    _persist_paths(connection, run_id, result)
    _persist_history(connection, run_id, previous, result)


def _release_unique_values(connection, previous, result):
    for owner, row in result.items.items():
        old = previous.items.get(owner)
        if old and old["grouping_key"] != row["grouping_key"]:
            connection.execute("UPDATE item SET grouping_key = %s WHERE id = %s", (f"temporary:{owner}", owner))
    for image_id, row in result.images.items():
        old = previous.images.get(image_id)
        if old and (old["relative_path"], old["state"]) != (row["relative_path"], row["state"]):
            connection.execute("UPDATE image SET relative_path = %s WHERE id = %s", (f"temporary:{image_id}", image_id))


def _upsert(connection, table, row, keys):
    columns = list(row)
    updates = [name for name in columns if name not in keys]
    query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) ON CONFLICT ({}) DO UPDATE SET {}").format(
        sql.Identifier(table), sql.SQL(", ").join(map(sql.Identifier, columns)),
        sql.SQL(", ").join(sql.Placeholder() for _ in columns),
        sql.SQL(", ").join(map(sql.Identifier, keys)),
        sql.SQL(", ").join(sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(name), sql.Identifier(name)) for name in updates),
    )
    connection.execute(query, tuple(Jsonb(value, dumps=_json_dumps) if isinstance(value, (Mapping, list)) else value
                                    for value in row.values()))


def _persist_identifiers(connection, run, previous, result):
    for owner, rows in result.identifiers.items():
        retained = {row["id"]: row for row in rows if "id" in row}
        for old in previous.identifiers.get(owner, []):
            if old["id"] not in retained:
                if old["state"] == "pending":
                    # 候选号从未持有，撤销不冒充曾用号；过去批次的独立 JSON 快照仍保留。
                    connection.execute("DELETE FROM identifier WHERE id = %s", (old["id"],))
                else:
                    connection.execute("UPDATE identifier SET state = 'historical', until_run = %s WHERE id = %s", (run, old["id"]))
            elif retained[old["id"]]["field_basis"] != old["field_basis"]:
                connection.execute("UPDATE identifier SET field_basis = %s WHERE id = %s",
                                   (Jsonb(retained[old["id"]]["field_basis"], dumps=_json_dumps), old["id"]))
        for row in rows:
            if "id" not in row:
                columns = list(row)
                query = sql.SQL("INSERT INTO identifier ({}) VALUES ({}) RETURNING id").format(
                    sql.SQL(", ").join(map(sql.Identifier, columns)), sql.SQL(", ").join(sql.Placeholder() for _ in columns))
                row["id"] = connection.execute(query, tuple(Jsonb(v, dumps=_json_dumps) if isinstance(v, dict) else v for v in row.values())).fetchone()["id"]


def _persist_relations(connection, result):
    for row in result.links.values():
        _upsert(connection, "item_image", row, ("item_id", "image_id"))
    # 正式事务内刷新当前派生关系；历史快照持有旧关系。
    connection.execute("DELETE FROM derivation")
    for row in result.derivations.values():
        _upsert(connection, "derivation", row, ("image_id", "source_image_id"))
    for owner, attachments in result.item_attachments.items():
        connection.execute("DELETE FROM item_attachment WHERE item_id = %s", (owner,))
        for attachment in attachments:
            connection.execute("INSERT INTO item_attachment VALUES (%s, %s)", (owner, attachment))


def _persist_paths(connection, run, result):
    for event in result.image_resolution.events:
        if event.kind in {"new", "moved"}:
            connection.execute("UPDATE image_path_history SET until_run = %s WHERE image_id = %s AND until_run IS NULL",
                               (run, event.image_id))
            connection.execute("INSERT INTO image_path_history VALUES (%s, %s, %s, %s, NULL)",
                               (event.image_id, event.current.root, str(event.current.relative_path), run))


def _relation_index(links, derivations):
    by_item, by_image, by_output = defaultdict(list), defaultdict(list), defaultdict(list)
    for (owner, image), row in links.items():
        by_item[owner].append(row)
        by_image[image].append(row)
    for (image, _), row in derivations.items():
        by_output[image].append(row)
    return by_item, by_image, by_output


def _snapshot(kind, object_id, rows, identifiers, relations, attachments):
    row = dict(rows[object_id])
    if kind == "item":
        row.pop("updated_run", None)
        # 数据库读取顺序不代表编号变化；按去掉数据库 ID 后的完整语义稳定排序。
        row["identifiers"] = sorted(
            _json_value([{k: v for k, v in ident.items() if k not in {"id", "until_run"}}
                         for ident in identifiers.get(object_id, [])]),
            key=lambda ident: json.dumps(ident, ensure_ascii=False, sort_keys=True),
        )
        row["images"] = sorted(relations[0][object_id], key=lambda r: str(r["image_id"]))
        row["attachments"] = sorted(map(str, attachments.get(object_id, set())))
    else:
        row.pop("last_seen", None)  # 被扫描并不是内容变化。
        row["derivations"] = sorted(relations[2][object_id], key=lambda r: str(r["source_image_id"]))
        row["items"] = sorted(relations[1][object_id], key=lambda r: str(r["item_id"]))
    return _json_value(row)


def _persist_history(connection, run, previous, result):
    current_relations = _relation_index(result.links, result.derivations)
    old_relations = _relation_index(previous.links, previous.derivations)
    events = defaultdict(list)
    for event in result.image_resolution.events:
        events[event.image_id].append({"kind": event.kind, "at": event.at.isoformat()})
    for kind, rows, old_rows in (("item", result.items, previous.items), ("image", result.images, previous.images)):
        for object_id, row in rows.items():
            snapshot = _snapshot(kind, object_id, rows, result.identifiers, current_relations, result.item_attachments)
            old = _snapshot(kind, object_id, old_rows, previous.identifiers, old_relations, previous.attachments) if object_id in old_rows else None
            if snapshot != old:
                if kind == "image":
                    snapshot["events"] = events[object_id]
                elif row["updated_run"] != run:
                    row["updated_run"] = run
                    connection.execute("UPDATE item SET updated_run = %s WHERE id = %s", (run, object_id))
                connection.execute("INSERT INTO history VALUES (%s, %s, %s, %s, %s)",
                                   (kind, object_id, run, Jsonb(snapshot, dumps=_json_dumps), Jsonb(row["field_basis"], dumps=_json_dumps)))
            if kind == "item" and row["provenance"] != old_rows.get(object_id, {}).get("provenance"):
                connection.execute("INSERT INTO provenance_history(item_id, run_id, value, field_basis) VALUES (%s, %s, %s, %s)",
                                   (object_id, run, Jsonb(row["provenance"], dumps=_json_dumps),
                                    Jsonb(row["field_basis"]["provenance"], dumps=_json_dumps)))


def value_at_run(connection: Connection, object_kind: str, object_id: UUID, run_id: int) -> dict | None:
    """只读变化时快照；不存在返回 None，不重新解析任何源文件。"""
    row = connection.execute("""
        SELECT h.snapshot, h.field_basis, h.run_id FROM history h
        WHERE object_kind = %s AND object_id = %s AND run_id <= %s ORDER BY run_id DESC LIMIT 1
    """, (object_kind, object_id, run_id)).fetchone()
    return row


def _changed(row, old, ignored=frozenset()):
    return _json_value({k: v for k, v in row.items() if k not in ignored}) != _json_value({k: v for k, v in old.items() if k not in ignored})


def _json_default(obj):
    if isinstance(obj, (UUID, PurePosixPath)):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Mapping):
        return dict(obj)
    return asdict(obj)


def _json_dumps(value):
    return json.dumps(value, default=_json_default, ensure_ascii=False)


def _json_value(value):
    return json.loads(_json_dumps(value))


def _anomaly(category, object_kind, object_key, root, path, raw, description):
    return dict(category=category, object_kind=object_kind, object_key=str(object_key), root=root,
                relative_path=str(path) if path is not None else None, raw=raw, description=description)


def _collect_anomalies(result):
    anomalies = []
    for issue in result.units.issues:
        if issue.category != "无馆藏号的写卷单元":
            anomalies.append(_anomaly(issue.category, "unit", f"{issue.root}:{issue.relative_path}",
                                      issue.root, issue.relative_path, issue.relative_path.name, issue.reason))
    for unit in result.units.units:
        if not unit.parsed.keys:
            anomalies.append(_anomaly("无馆藏号的写卷单元", "unit", unit.key, unit.root, unit.relative_path, unit.name, "不自动合并"))
        for ident in unit.parsed.identifiers:
            if ident.system in {"pelliot", "nlc"} and not ident.compliant:
                anomalies.append(_anomaly("编号存疑", "unit", unit.key, unit.root, unit.relative_path, ident.raw, "不作主编号或归并依据"))
        for raw in unit.parsed.suspected:
            anomalies.append(_anomaly("疑似编号", "unit", unit.key, unit.root, unit.relative_path, raw, "裸四位数，不自动认定"))
    # 国图覆盖后已取得合规编号的单元不再是无号合并候选。
    keyed = {unit.key for unit in result.units.units if unit.parsed.keys}
    for suggestion in result.units.suggestions:
        if suggestion.left not in keyed and suggestion.right not in keyed:
            # 建议仍只有一对，不改变归并；异常按参与端各记一条，供查询准确关联。
            for endpoint in (suggestion.left, suggestion.right):
                anomalies.append(_anomaly("合并建议", "unit", endpoint, None, None,
                                          suggestion.left + "；" + suggestion.right, suggestion.reason))
    for value in result.nlc.values():
        for issue in value.issues:
            anomalies.append(_anomaly(issue.category, "file", f"{issue.root}:{issue.relative_path}",
                                      issue.root, issue.relative_path, issue.raw, issue.reason))
    for issue in result.derivation.issues:
        anomalies.append(_anomaly(issue.category, "file", issue.evidence_file or f"{issue.root}:{issue.relative_path}",
                                  issue.root, issue.relative_path, issue.raw, issue.reason))
    for file, reading in result.readings.items():
        if reading.error:
            anomalies.append(_anomaly("读不了的文件", "image", f"{file.root}:{file.relative_path}", file.root,
                                      file.relative_path, file.relative_path.name, reading.error))
        elif rules.detect_lineage(reading, result.derivation.outputs).unresolved:
            anomalies.append(_anomaly("谱系未判定", "image", f"{file.root}:{file.relative_path}", file.root,
                                      file.relative_path, file.relative_path.name, "没有命中谱系规则"))
    for owner, reasons in result.item_resolution.pending.items():
        anomalies.append(_anomaly("身份待确认", "item", owner, None, None, result.items[owner]["grouping_key"] or "", "；".join(reasons)))
    for owner, row in result.items.items():
        if row["provenance"]["evidence_conflict"]:
            anomalies.append(_anomaly("出处证据冲突", "item", owner, None, None,
                                      "；".join(row["provenance"]["evidence"]), "合规馆藏号与非敦煌线索并存"))
    for excluded in result.units.excluded:
        anomalies.append(_anomaly("未导入的文件", "file", f"{excluded.root}:{excluded.relative_path}",
                                  excluded.root, excluded.relative_path, excluded.relative_path.name, excluded.reason))
    return anomalies


def build_report(result: ImportComputation, previous: CatalogState, fetch: IndexFetch,
                 latest_snapshot: IndexSnapshot | None = None) -> dict:
    """仅输出本批计数与覆盖事实；不含 NAS 基线对照算法。"""
    present = [row for row in result.images.values() if row["state"] == "present"]
    summaries = rules.summarize_lineages([(file, rules.detect_lineage(reading, result.derivation.outputs))
                                         for file, reading in result.readings.items()])
    current_dirs = {path for root, path in summaries if root == "data"}
    mapped = {file.relative_path.parent for unit in result.units.units if result.item_resolution.unit_items[unit.key]
              for member in unit.images for file in (member.file,) if file.root == "data" and file.kind == "tiff"}
    coverage = _coverage(fetch, result.inventory, current_dirs, mapped)
    anomalies = list(result.anomalies)
    if fetch.snapshot is None:
        anomalies.append(_anomaly("v0 索引不可用", "import", "v0", None, None, "", fetch.error or "未取得有效快照"))
    events = Counter(event.kind for event in result.image_resolution.events)
    current_relations = _relation_index(result.links, result.derivations)
    old_relations = _relation_index(previous.links, previous.derivations)
    changed_items = sum(
        _snapshot("item", owner, result.items, result.identifiers, current_relations, result.item_attachments)
        != _snapshot("item", owner, previous.items, previous.identifiers, old_relations, previous.attachments)
        for owner in result.items.keys() & previous.items.keys()
    )
    metadata_changed = sum(
        _snapshot("image", image, result.images, {}, current_relations, {})
        != _snapshot("image", image, previous.images, {}, old_relations, {})
        for image in result.images.keys() & previous.images.keys()
    )
    # 只汇总规则已经给出的证据标签，不再匹配目录 / 文件名做第二套出处判断。
    suggestion_units = defaultdict(set)
    for row in result.items.values():
        for evidence in row["provenance"]["suggestion_evidence"]:
            unit_key, _, label = evidence.rpartition("：")
            suggestion_units[unit_key].add(label)
    doubtful_pelliot = {i.normalized for u in result.units.units for i in u.parsed.identifiers
                        if i.system == "pelliot" and not i.compliant}
    counts = {
        "items": len(result.items), "images": len(result.images), "present_images": len(present),
        "images_by_kind": dict(Counter(row["kind"] for row in present)),
        "images_by_lineage": dict(Counter(row["lineage"] for row in present)),
        "images_by_role": dict(Counter(member.role for unit in result.units.units for member in unit.images)),
        "missing_images": len(result.images) - len(present),
        "items_by_provenance": dict(Counter(row["provenance"]["status"] for row in result.items.values())),
        "image_directories": len(current_dirs),
        "directories_by_lineage": dict(Counter(value for (root, _), value in summaries.items() if root == "data")),
        "data_tiff": sum(f.root == "data" and f.kind == "tiff" for f in result.inventory.images),
        "backup_tiff": sum(f.root == "backup" and f.kind == "tiff" for f in result.inventory.images),
        "psb": sum(f.kind == "psb" for f in result.inventory.images),
        "page_jpg": sum(m.role == "页图" for u in result.units.units for m in u.images),
        "preview_jpg": sum(f.kind == "jpg" and f.relative_path.name.endswith("_preview.jpg") for f in result.inventory.images),
        "attachments_by_kind": dict(Counter(f.kind for f in result.inventory.attachments)),
        "hidden_files": sum(f.hidden for f in result.inventory.images),
        "loose_files": sum(any(m.file.relative_path == u.relative_path for m in u.images) for u in result.units.units),
        "multi_number_units": sum(len(u.parsed.keys) > 1 for u in result.units.units),
        "wb_units": sum(any(i.system == "sharer" and i.normalized.startswith("WB ") for i in u.parsed.identifiers) for u in result.units.units),
        "wa_units": sum(any(i.system == "sharer" and i.normalized.startswith("WA ") for i in u.parsed.identifiers) for u in result.units.units),
        "anomalies": len(anomalies), "anomalies_by_category": dict(Counter(a["category"] for a in anomalies)),
        "changes": {"images": {**{kind: events[kind] for kind in ("new", "changed", "moved", "missing", "reappeared")},
                               "metadata_changed": metadata_changed},
                    "items": {"new": len(result.items.keys() - previous.items.keys()), "changed": changed_items}},
        "facts_reused": sum(r.reused for r in result.readings.values()),
        "doubtful_pelliot_numbers": sorted(doubtful_pelliot),
        "doubtful_pelliot_number_count": len(doubtful_pelliot),
        "suspected_number_occurrences": sum(len(u.parsed.suspected) for u in result.units.units),
        "parts_by_parent": dict(Counter(parent for item in result.item_resolution.items
                                         for parent in {s.value.parent for s in item.identifiers
                                                        if s.value.key == item.grouping_key and s.value.parent})),
        "items_by_primary_number": dict(Counter(next((s.value.normalized for s in item.identifiers
                                                      if item.grouping_key is not None and s.value.key == item.grouping_key), "无主编号")
                                                for item in result.item_resolution.items)),
        "items_by_doubtful_number": dict(Counter(number for item in result.item_resolution.items
                                                 for number in {s.value.normalized for s in item.identifiers
                                                                if s.value.system in {"pelliot", "nlc"} and not s.value.compliant})),
        "excluded_jpg": sum(entry.relative_path.suffix.lower() == ".jpg" for entry in result.units.excluded),
        "merged_scrolls": sum(member.role == "合并长卷" for unit in result.units.units for member in unit.images),
        "outputs_with_derivation": len({edge.output for edge in result.derivation.edges}),
        "nlc_tiff": sum(f.kind == "tiff" and f.relative_path.parts[0] == rules.NLC_CATEGORY for f in result.inventory.images),
        "nlc_tiff_with_canvas": sum(row["kind"] == "tiff" and row["relative_path"].split("/")[0] == rules.NLC_CATEGORY
                                    and row["canvas_id"] is not None for row in present),
        "non_dunhuang_suggestions": sum(row["provenance"]["suggestion"] == "非敦煌" for row in result.items.values()),
        "kaibao_suggestion_units": sum(any("开宝藏" in label for label in labels) for labels in suggestion_units.values()),
        "title_clue_suggestion_units": sum(any("开宝藏" not in label for label in labels) for labels in suggestion_units.values()),
        "excluded": len(result.units.excluded),
        "unassigned_attachments": len(result.units.unassigned_attachments),
    }
    return dict(counts=counts, anomalies=anomalies, excluded=_json_value(result.units.excluded),
                unassigned_attachments=[{"root": f.root, "relative_path": str(f.relative_path), "id": str(result.attachments[f])}
                                        for f in result.units.unassigned_attachments],
                new_categories=result.units.new_categories, coverage=coverage,
                suggestion_unit_evidence={key: sorted(labels) for key, labels in suggestion_units.items()},
                latest_valid_snapshot_available=latest_snapshot is not None,
                directory_lineages=[{"root": root, "relative_path": str(path), "lineage": value} for (root, path), value in summaries.items()],
                cache_access=[str(path) for path in result.derivation.opened_paths])


def _coverage(fetch, inventory, current_dirs, mapped):
    if fetch.snapshot is None:
        return {"status": "unavailable", "reason": fetch.error, "unmapped_existing": None,
                "unmapped_existing_count": None, "disk_not_indexed": None, "index_directory_absent": None}
    indexed = set(fetch.snapshot.volumes)
    existing = indexed & inventory.directories.get("data", set())
    return {"status": "valid", "reason": None, "unmapped_existing": sorted(map(str, existing - mapped)),
            "unmapped_existing_count": len(existing - mapped),
            "disk_not_indexed": sorted(map(str, current_dirs - indexed)),
            "index_directory_absent": sorted(map(str, indexed - inventory.directories.get("data", set())))}


def _save_report_details(connection, run, result, report):
    for anomaly in report["anomalies"]:
        connection.execute("""INSERT INTO anomaly(run_id, category, object_kind, object_key, root, relative_path, raw, description)
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""", (run, *anomaly.values()))
    for entry in result.units.excluded:
        connection.execute("INSERT INTO excluded VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
                           (run, entry.root, str(entry.relative_path), entry.reason))


def _finish_run(connection, run, status, report, error=None):
    connection.execute("""
        UPDATE import_run SET ended_at = now(), status = %s, counts = %s, health_summary = %s,
                              cache_access = %s, error = %s WHERE id = %s
    """, (status, Jsonb(report, dumps=_json_dumps), Jsonb(report.get("health", {}), dumps=_json_dumps),
          Jsonb(report.get("cache_access", []), dumps=_json_dumps), error, run))


def read_report(connection: Connection, run_id: int | None = None) -> dict | None:
    """只读已有批次；counts 列存完整报告，其 counts 子键为可供 compare 消费的计数。"""
    if run_id is None:
        row = connection.execute("SELECT * FROM import_run ORDER BY id DESC LIMIT 1").fetchone()
    else:
        row = connection.execute("SELECT * FROM import_run WHERE id = %s", (run_id,)).fetchone()
    return _json_value(row) if row is not None else None
