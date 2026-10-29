"""私有紧凑表示的真实读契约、形状容量与 JSON 边界。"""

from collections.abc import Mapping
from datetime import UTC, datetime
import gc
import json
from pathlib import PurePosixPath
from uuid import UUID
import weakref

import pytest

from dh_catalog._compact import CompactMap, ShapePool
from dh_catalog.importer import _BasisPool, _json_dumps, _json_value
from dh_catalog.scan import Fact


@pytest.mark.parametrize("source", [
    {}, {"only": None}, {"a": 1, "b": 2}, {"b": 2, "a": 1},
    {"a": 1, "extra": [True, 1, 1.0]}, {"extra": "原文"},
])
def test_complete_mapping_read_contract(source):
    pool = ShapePool()
    compact = pool.compact(source)
    assert isinstance(compact, Mapping) and not isinstance(compact, dict)
    assert not hasattr(compact, "__dict__")
    assert CompactMap.__slots__ == ("_shape", "_values")
    assert type(compact._values) is tuple
    assert compact._shape.keys == tuple(source)
    assert len(compact) == len(source)
    assert list(compact) == list(source)
    assert list(compact.items()) == list(source.items())
    assert list(compact.values()) == list(source.values())
    assert dict(compact) == source
    assert compact == source and source == compact
    for key, value in source.items():
        assert key in compact and compact[key] is value and compact.get(key) is value
    absent = object()
    with pytest.raises(KeyError):
        compact[absent]
    assert compact.get(absent, absent) is absent
    assert compact.get(absent) is None and absent not in compact
    with pytest.raises(TypeError):
        compact["a"] = 3
    with pytest.raises(TypeError):
        del compact["a"]


def test_shapes_preserve_order_and_do_not_cache_values():
    pool = ShapePool()
    first = pool.compact({"a": 1, "b": 2})
    second = pool.compact({"a": 10, "b": 20})
    reverse = pool.compact({"b": 200, "a": 100})
    extra = pool.compact({"a": 1, "b": 2, "extra": 3})
    missing = pool.compact({"b": 4})
    assert first is not second and first._shape is second._shape
    assert reverse._shape is not first._shape
    assert list(reverse) == ["b", "a"] and list(reverse.values()) == [200, 100]
    assert first == {"a": 1, "b": 2} and second == {"a": 10, "b": 20}
    assert dict(extra) == {"a": 1, "b": 2, "extra": 3} and dict(missing) == {"b": 4}
    source = {"a": 30, "b": 40}
    frozen = pool.compact(source)
    source["a"] = 99
    assert frozen["a"] == 30
    # 池只保留形状，不钉住某行的任意值。
    class Payload:
        pass
    payload = Payload()
    ref = weakref.ref(payload)
    row = pool.compact({"payload": payload})
    del row, payload
    assert ref() is None


def test_shape_pool_is_exact_order_lru_bounded_and_eviction_keeps_old_maps():
    pool = ShapePool()
    rows = [pool.compact({f"key-{n}": n}) for n in range(64)]
    assert len(pool._shapes) == 64
    touched = pool.compact({"key-0": "new value"})
    assert touched._shape is rows[0]._shape
    pool.compact({"key-64": 64})
    assert len(pool._shapes) == 64
    assert ("key-0",) in pool._shapes and ("key-1",) not in pool._shapes
    recreated = pool.compact({"key-1": "recreated"})
    assert recreated._shape is not rows[1]._shape
    for n, row in enumerate(rows):
        assert row == {f"key-{n}": n}
    for n in range(65, 200):
        pool.compact({f"key-{n}": n})
    assert len(pool._shapes) == 64
    assert rows[0]["key-0"] == 0 and touched["key-0"] == "new value"


def test_nested_compact_maps_are_shallow_and_idempotent():
    pool = _BasisPool()
    leaf = {"status": "value", "value": [7, 5]}
    basis_leaf = {"source_images": ["second", "first"], "run": 1}
    row = pool.compact_image({"facts": {"pixel_size": leaf},
                              "field_basis": {"facts": {"pixel_size": basis_leaf}}, "extra": True})
    expected = {"facts": {"pixel_size": leaf},
                "field_basis": {"facts": {"pixel_size": basis_leaf}}, "extra": True}
    assert row == expected and expected == row
    for mapping in (row, row["facts"], row["field_basis"], row["field_basis"]["facts"]):
        assert isinstance(mapping, CompactMap)
        assert pool.shapes.compact(mapping) is mapping
    assert row["facts"]["pixel_size"] is leaf
    assert row["field_basis"]["facts"]["pixel_size"] is basis_leaf
    assert type(leaf) is dict and type(leaf["value"]) is list
    assert basis_leaf["source_images"] == ["second", "first"]
    # 新 builder 可以已有紧凑嵌套映射；缺失分支只替换需变的外层。
    again = pool.compact_image(dict(row))
    missing = dict(row, state="missing")
    missing["field_basis"] = dict(row["field_basis"], state={"run": 2})
    missing = pool.compact_image(missing)
    assert again["field_basis"] is row["field_basis"]
    assert missing["facts"] is row["facts"]
    assert missing["field_basis"]["facts"] is row["field_basis"]["facts"]
    assert missing["field_basis"] is not row["field_basis"]
    assert "state" not in row
    # 旧依据可以缺少 facts 键；只转换实际存在的映射，不补造字段。
    sparse = {"extra": None, "facts": {}, "field_basis": {"custom": basis_leaf}}
    compact_sparse = pool.compact_image(dict(sparse))
    assert dict(compact_sparse) == sparse and list(compact_sparse) == list(sparse)
    assert list(compact_sparse["field_basis"]) == ["custom"]


def test_json_boundary_preserves_nested_types_and_existing_conversions():
    pool = ShapePool()
    identity = UUID("d59ea6b4-08b8-4201-b3ef-871e610f9714")
    at = datetime(2026, 10, 29, 12, 34, 56, tzinfo=UTC)
    path = PurePosixPath("敦煌003/原文 ＋---/.图.tif")
    row = pool.compact({"nested": pool.compact({"id": identity, "at": at, "path": path}),
                        "values": [True, 1, 1.0, None, "原文"], "fact": Fact("value", (7, 5))})
    expected = {"nested": {"id": str(identity), "at": at.isoformat(), "path": str(path)},
                "values": [True, 1, 1.0, None, "原文"], "fact": {"status": "value", "value": [7, 5]}}
    decoded = _json_value(row)
    assert json.dumps(decoded, sort_keys=True) == json.dumps(expected, sort_keys=True)
    assert json.loads(_json_dumps(row)) == decoded
    assert type(decoded) is type(decoded["nested"]) is type(decoded["fact"]) is dict
    assert type(decoded["values"]) is type(decoded["fact"]["value"]) is list
    assert [type(v) for v in decoded["values"][:3]] == [bool, int, float]
    for encode in (_json_value, _json_dumps):
        with pytest.raises(TypeError):
            encode(pool.compact({"unknown": object()}))


@pytest.mark.parametrize("basis_pool", [False, True])
def test_live_map_does_not_retain_pool_or_cross_batch_values_without_gc(basis_pool):
    enabled = gc.isenabled()
    try:
        gc.disable()
        owner = _BasisPool() if basis_pool else ShapePool()
        pool = owner.shapes if basis_pool else owner
        owner_ref, pool_ref = weakref.ref(owner), weakref.ref(pool)
        row = pool.compact({"run": 1, "list": [1]})
        del pool, owner
        assert owner_ref() is None and pool_ref() is None
        next_pool = ShapePool()
        next_row = next_pool.compact({"run": 2, "list": [2]})
        assert next_row._shape is not row._shape
        assert dict(row) == {"run": 1, "list": [1]}
        assert dict(next_row) == {"run": 2, "list": [2]}
    finally:
        if enabled:
            gc.enable()
        else:
            gc.disable()
