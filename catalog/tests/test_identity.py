import os
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath
from typing import NamedTuple
from uuid import UUID

import pytest

from dh_catalog.identity import ImageResolution, ItemResolution, resolve_images, resolve_items
from dh_catalog.scan import scan
from dh_catalog.units import UnitsResult, build_units

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)


def test_reimport_keeps_ids(roots, make_image):
    make_image(roots["data"] / "敦煌003/P.2800/1.tif")
    first = _catalog(roots)
    second = _catalog(roots, first)
    assert [i.id for i in first.images.images] == [i.id for i in second.images.images]
    assert first.items.items == second.items.items
    assert not second.items.pending and not second.items.number_changes
    assert not second.images.events
    assert second.images.images[0].first_seen == 1 and second.images.images[0].last_seen == 2
    assert first.images.images[0].last_seen == 1  # 不修改 S0。


def test_ids_not_path_derived(roots, make_image):
    make_image(roots["data"] / "敦煌003/P.2800/1.tif")
    files = scan(roots).images
    first = resolve_images([], files, 1, NOW).images[0]
    independent = resolve_images([], files, 1, NOW).images[0]
    assert isinstance(first.id, UUID) and first.id.version == 4
    assert first.id != independent.id


@pytest.mark.parametrize("operation", ["rename", "move", "swap"])
def test_rename_move_and_swap(roots, make_image, operation):
    data = roots["data"]
    a = data / "188敦煌001/2018年/P.2002"
    b = data / "188敦煌001/2018年/P.2003"
    make_image(a / "1.tif")
    make_image(b / "1.tif", software="different")
    first = resolve_images([], scan(roots).images, 1, NOW)
    by_inode = {i.file.inode: i.id for i in first.images}
    if operation == "rename":
        a.rename(a.with_name("P.2004"))
    elif operation == "move":
        destination = data / "188敦煌001/2019年新增1/P.2002"
        destination.parent.mkdir(parents=True)
        a.rename(destination)
    else:
        temp = a.with_name("temporary")
        a.rename(temp)
        b.rename(a)
        temp.rename(b)
    files = scan(roots).images
    second = resolve_images(first.images, list(reversed(files)), 2, NOW)
    assert {i.file.inode: i.id for i in second.images} == by_inode
    moved = [event for event in second.events if event.kind == "moved"]
    assert len(moved) == (2 if operation == "swap" else 1)
    assert all(event.previous.relative_path != event.current.relative_path for event in moved)
    assert not any(event.kind in {"new", "missing"} for event in second.events)
    assert all(i.file.relative_path.parts[1] == "2018年" for i in first.images)


def test_changed_file_uses_position_and_keeps_id(roots, make_image):
    path = make_image(roots["data"] / "敦煌003/P.2800/合并长卷.tif", software="first")
    first = resolve_images([], scan(roots).images, 1, NOW)
    old = first.images[0]
    replacement = make_image(path.parent / ".replacement.tif", software="a different version")
    os.replace(replacement, path)
    second = resolve_images(first.images, scan(roots).images, 2, NOW)
    assert len(second.images) == 1
    assert second.images[0].id == old.id
    assert second.images[0].file.inode != old.file.inode
    assert [event.kind for event in second.events] == ["changed"]
    assert second.events[0].previous == old.file
    assert second.events[0].current == second.images[0].file


@pytest.mark.parametrize("destination", ["敦煌003/P.2800/1.tif", "敦煌003/新位置/1.tif"])
def test_reappearance(roots, make_image, destination):
    data = roots["data"]
    path = make_image(data / "敦煌003/P.2800/1.tif")
    first = resolve_images([], scan(roots).images, 1, NOW)
    recycled = data / "#recycle/1.tif"
    recycled.parent.mkdir()
    path.rename(recycled)
    missing_at = NOW + timedelta(minutes=1)
    second = resolve_images(first.images, scan(roots).images, 2, missing_at)
    assert len(second.images) == 1
    assert second.images[0].missing_since == missing_at
    assert second.images[0].last_seen == 1
    assert [event.kind for event in second.events] == ["missing"]
    third = resolve_images(second.images, scan(roots).images, 3, NOW + timedelta(minutes=2))
    assert not third.events
    assert third.images[0].missing_since == missing_at
    restored = data / destination
    restored.parent.mkdir(parents=True, exist_ok=True)
    recycled.rename(restored)
    fourth = resolve_images(third.images, scan(roots).images, 4, NOW + timedelta(minutes=3))
    assert fourth.images[0].id == first.images[0].id
    assert fourth.images[0].missing_since is None
    assert fourth.images[0].file.relative_path == PurePosixPath(destination)
    kinds = {event.kind for event in fourth.events}
    assert "reappeared" in kinds and "new" not in kinds
    assert ("moved" in kinds) is (destination != "敦煌003/P.2800/1.tif")


def test_signature_match_precedes_position_fallback(roots, make_image):
    data = roots["data"]
    path = make_image(data / "敦煌003/P.2800/1.tif", software="original")
    first = resolve_images([], scan(roots).images, 1, NOW)
    moved = path.with_name("2.tif")
    path.rename(moved)
    make_image(path, software="new file at old position")
    second = resolve_images(first.images, scan(roots).images, 2, NOW)
    images = {image.file.relative_path.name: image for image in second.images}
    assert images["2.tif"].id == first.images[0].id
    assert images["1.tif"].id != first.images[0].id
    assert sorted(event.kind for event in second.events) == ["moved", "new"]


def test_roots_are_separate_identity_namespaces(roots, make_image):
    path = make_image(roots["data"] / "敦煌003/P.2800/1.tif")
    first = resolve_images([], scan(roots).images, 1, NOW)
    destination = roots["backup"] / "敦煌003/P.2800/1.tif"
    destination.parent.mkdir(parents=True)
    path.rename(destination)
    second = resolve_images(first.images, scan(roots).images, 2, NOW)
    assert len(second.images) == 2
    present = next(i for i in second.images if i.missing_since is None)
    missing = next(i for i in second.images if i.missing_since is not None)
    assert missing.id == first.images[0].id
    assert present.id != first.images[0].id
    assert {event.kind for event in second.events} == {"new", "missing"}


class CatalogSnapshot(NamedTuple):
    images: ImageResolution
    items: ItemResolution
    units: UnitsResult
    run: int

    @property
    def by_key(self):
        return {item.grouping_key: item for item in self.items.items if item.grouping_key is not None}

    @property
    def by_id(self):
        return {item.id: item for item in self.items.items}


def _catalog(roots, previous=None, reverse=False):
    """只编排真实生产函数；不在测试里再写归并算法。"""
    inventory = scan(roots)
    units = build_units(inventory)
    run = previous.run + 1 if previous else 1
    files = list(reversed(inventory.images)) if reverse else inventory.images
    images = resolve_images(previous.images.images if previous else [], files, run, NOW + timedelta(minutes=run))
    ordered_units = list(reversed(units.units)) if reverse else units.units
    prior_items = previous.items.items if previous else []
    if reverse:
        prior_items = list(reversed(prior_items))
    items = resolve_items(prior_items, ordered_units, images.images)
    return CatalogSnapshot(images, items, units, run)


def test_same_number_merged_across_lineages(roots, make_image):
    make_image(roots["data"] / "188敦煌001/2018年/P.2002 加工图/1.tif", software="Photoshop")
    make_image(roots["data"] / "188敦煌001/2019年新增1/P.2002 原图/native.tif")
    catalog = _catalog(roots)
    assert len(catalog.items.items) == 1
    item = catalog.by_key["pelliot:2002"]
    assert item.id.version == 4 and len(item.image_ids) == 2
    assert set(catalog.items.unit_items) == {
        "data:188敦煌001/2018年/P.2002 加工图", "data:188敦煌001/2019年新增1/P.2002 原图",
    }
    assert all(owners == {item.id} for owners in catalog.items.unit_items.values())
    assert {i.value.normalized for i in item.identifiers} == {"P.2002"}


def test_multi_number_units_share_images(roots, make_image):
    make_image(roots["data"] / "敦煌003/P3012+5564/1.tif")
    first = _catalog(roots)
    assert set(first.by_key) == {"pelliot:3012", "pelliot:5564"}
    a, b = first.by_key["pelliot:3012"], first.by_key["pelliot:5564"]
    assert a.id != b.id and a.image_ids == b.image_ids
    assert a.clues == b.clues == ("名称所示的合装或缀合",)
    assert {i.value.key for i in a.identifiers} == {"pelliot:3012"}
    assert {i.value.key for i in b.identifiers} == {"pelliot:5564"}
    second = _catalog(roots, first)
    assert second.items.items == first.items.items
    assert not second.items.pending


def test_parts_and_parent(roots, make_image):
    for name in ("P.2504", "P.2504-1Pièce", "P.2504-2", "P.2504-3", "P.2504-4", "P.2222A"):
        make_image(roots["data"] / "敦煌003" / name / "1.tif")
    for name in ("BD00023", "BD00023a"):
        make_image(roots["data"] / "中国国博馆藏" / name / "1.tif")
    first = _catalog(roots)
    parent = first.by_key["pelliot:2504"]
    assert parent.parent_id is None
    assert all(first.by_key[f"pelliot:2504:{i}"].parent_id == parent.id for i in range(1, 5))
    assert first.by_key["nlc:BD00023a"].parent_id == first.by_key["nlc:BD00023"].id
    assert first.by_key["pelliot:2222:A"].parent_id is None
    make_image(roots["data"] / "敦煌003/P.2222/1.tif")
    second = _catalog(roots, first)
    assert second.by_key["pelliot:2222:A"].parent_id == second.by_key["pelliot:2222"].id
    assert second.by_key["pelliot:2222:A"].id == first.by_key["pelliot:2222:A"].id


def test_doubtful_numbers_not_merged(roots, make_image):
    for name in ("P.0901 绢画", "P.0901 梵文写经", "P.0901 坐佛像", "WB 29 A", "WB 29 B"):
        make_image(roots["data"] / "188敦煌001/2018年" / name / "1.tif")
    first = _catalog(roots)
    assert len(first.items.items) == 5
    assert all(i.grouping_key is None for i in first.items.items)
    assert all(len(i.image_ids) == 1 for i in first.items.items)
    assert sum(any(i.value.normalized == "P.0901" for i in item.identifiers) for item in first.items.items) == 3
    second = _catalog(roots, first)
    assert second.items.items == first.items.items


def test_number_change_keeps_id(roots, make_image):
    original = roots["data"] / "敦煌003/P.2602"
    make_image(original / "1.tif")
    first = _catalog(roots)
    old = first.by_key["pelliot:2602"]
    original.rename(original.with_name("P.2603"))
    second = _catalog(roots, first)
    assert set(second.by_key) == {"pelliot:2603"}
    updated = second.by_key["pelliot:2603"]
    assert (updated.id, updated.serial, updated.image_ids) == (old.id, old.serial, old.image_ids)
    assert [(c.item_id, c.before, c.after) for c in second.items.number_changes] == [
        (old.id, "pelliot:2602", "pelliot:2603"),
    ]
    assert first.by_key["pelliot:2602"] == old
    assert {i.value.normalized for i in updated.identifiers} == {"P.2603"}


@pytest.mark.parametrize("case", ["collision", "two_numbers", "foreign_images", "divergent_units", "number_removed"])
def test_unmatched_cases_kept_pending(roots, make_image, case):
    data = roots["data"]
    a = data / "敦煌003/P.2602"
    b = data / "敦煌003/P.2603"
    if case == "two_numbers":
        a = a.with_name("P3012+5564")
    make_image(a / "1.tif")
    if case in {"collision", "foreign_images"}:
        make_image(b / "2.tif", software="another item")
    if case == "divergent_units":
        make_image(data / "敦煌004/P.2602/2.tif")
    first = _catalog(roots)
    changed = a.with_name({
        "collision": "副本 P.2603", "two_numbers": "P3013+5565", "divergent_units": "P.2604",
    }.get(case, "无编号"))
    if case == "foreign_images":
        moved = b / "2.tif"
        destination = a / "2.tif"
        moved.rename(destination)
    else:
        a.rename(changed)
    second = _catalog(roots, first)
    assert {i.id: i.grouping_key for i in second.items.items} == {i.id: i.grouping_key for i in first.items.items}
    assert {i.id: i.image_ids for i in second.items.items} == {i.id: i.image_ids for i in first.items.items}
    assert second.items.pending
    assert all(reasons for reasons in second.items.pending.values())
    assert not second.items.number_changes
    for owner in second.items.pending:
        old = first.by_id[owner]
        if old.grouping_key:
            assert any(i.value.key == old.grouping_key for i in second.by_id[owner].identifiers)
    if case == "foreign_images":
        destination.rename(moved)
    else:
        changed.rename(a)
    third = _catalog(roots, second)
    assert not third.items.pending and not third.items.pending_identifiers
    assert third.items.items == first.items.items


@pytest.mark.parametrize("count", [2, 3])
def test_swap_and_rotation_order_independent(roots, make_image, count):
    base = roots["data"] / "敦煌003"
    names = [f"P.{2602 + i}" for i in range(count)]
    for name in names:
        make_image(base / name / "1.tif")
    first = _catalog(roots)
    for i, name in enumerate(names):
        (base / name).rename(base / f"temp{i}")
    for i, name in enumerate(names):
        (base / f"temp{i}").rename(base / names[(i + 1) % count])
    normal = _catalog(roots, first)
    reverse = _catalog(roots, first, reverse=True)
    assert normal.items.items == reverse.items.items
    assert normal.items.number_changes == reverse.items.number_changes
    assert not normal.items.pending and not reverse.items.pending
    assert len(normal.items.number_changes) == count
    for i in range(count):
        assert normal.by_key[f"pelliot:{2602 + (i + 1) % count}"].id == first.by_key[f"pelliot:{2602 + i}"].id


@pytest.mark.parametrize("existing_target", [False, True])
def test_multi_number_add_and_rewrite(roots, make_image, existing_target):
    base = roots["data"] / "敦煌003"
    directory = base / "P2661"
    make_image(directory / "1.tif")
    if existing_target:
        make_image(base / "P3735/2.tif")
    first = _catalog(roots)
    shared = base / "P2661(+3735)"
    directory.rename(shared)
    second = _catalog(roots, first)
    assert second.by_key["pelliot:2661"].id == first.by_key["pelliot:2661"].id
    assert first.by_key["pelliot:2661"].image_ids <= second.by_key["pelliot:3735"].image_ids
    if existing_target:
        assert second.by_key["pelliot:3735"].id == first.by_key["pelliot:3735"].id
    else:
        shared.rename(base / "P2661(+3736)")
        third = _catalog(roots, second)
        assert third.by_key["pelliot:3736"].id == second.by_key["pelliot:3735"].id
        assert third.by_key["pelliot:2661"].id == second.by_key["pelliot:2661"].id
        assert len(third.items.number_changes) == 1
    assert not second.items.pending


def test_new_images_assignment(roots, make_image):
    directory = roots["data"] / "敦煌003/无编号"
    make_image(directory / "1.tif")
    first = _catalog(roots)
    for name in ("2.tif", "3.tif", "4.tif"):
        make_image(directory / name)
    second = _catalog(roots, first)
    assert len(second.items.items) == 1
    assert second.items.items[0].id == first.items.items[0].id
    assert len(second.items.items[0].image_ids) == 4


@pytest.mark.parametrize("majority", [False, True])
def test_new_images_assignment_between_unkeyed_items(roots, make_image, majority):
    base = roots["data"] / "敦煌003"
    a, b = base / "卷A", base / "卷B"
    make_image(a / "a.tif")
    make_image(b / "b.tif")
    if majority:
        make_image(b / "b2.tif")
    first = _catalog(roots)
    owner_a, owner_b = first.items.items
    for path in b.iterdir():
        path.rename(a / path.name)
    new_file = make_image(a / "new.tif")
    second = _catalog(roots, first)
    image_id = next(i.id for i in second.images.images if i.file.relative_path.name == new_file.name)
    winner, other = (owner_b, owner_a) if majority else (owner_a, owner_b)
    assert image_id in second.by_id[winner.id].image_ids
    assert image_id not in second.by_id[other.id].image_ids
    assert len(second.items.items) == 2 and not second.items.pending


def test_multi_number_new_images_shared(roots, make_image):
    directory = roots["data"] / "敦煌003/P3012+5564"
    make_image(directory / "1.tif")
    first = _catalog(roots)
    make_image(directory / "2.tif")
    second = _catalog(roots, first)
    assert all(len(item.image_ids) == 2 for item in second.items.items)
    assert second.items.items[0].image_ids == second.items.items[1].image_ids


def test_entirely_missing_item_keeps_identifiers_and_clues(roots, make_image):
    directory = roots["data"] / "敦煌003/P3012+5564 WB29"
    path = make_image(directory / "1.tif")
    first = _catalog(roots)
    recycle = roots["data"] / "#recycle"
    recycle.mkdir()
    directory.rename(recycle / directory.name)
    second = _catalog(roots, first)
    assert second.items.items == first.items.items
    assert second.items.preserved_items == set(first.by_id)
    assert not second.items.number_changes
    (recycle / directory.name).rename(directory)
    third = _catalog(roots, second)
    assert path.exists()
    assert third.items.items == first.items.items
    assert not third.items.preserved_items


def test_pending_unit_does_not_associate_new_number_to_existing_holder(roots, make_image):
    data = roots["data"]
    a, b = data / "敦煌003/P2002", data / "敦煌003/P2003"
    make_image(a / "1.tif")
    make_image(b / "2.tif")
    first = _catalog(roots)
    renamed = a.with_name("副本 P2003")
    a.rename(renamed)
    make_image(renamed / "new.tif")
    second = _catalog(roots, first)
    old_owner = first.by_key["pelliot:2002"].id
    other_owner = first.by_key["pelliot:2003"].id
    assert set(second.items.pending) == {old_owner}
    assert {s.value.key for s in second.items.pending_identifiers[old_owner]} == {"pelliot:2003"}
    assert second.by_id[other_owner].image_ids == first.by_id[other_owner].image_ids
    assert len(second.by_id[old_owner].image_ids) == 2


def test_collision_rollback_propagates(roots, make_image):
    base = roots["data"] / "敦煌003"
    for number in (2602, 2603, 2604):
        make_image(base / f"P{number}" / "1.tif")
    first = _catalog(roots)
    (base / "P2602").rename(base / "副本 P2603")
    (base / "P2603").rename(base / "副本 P2604")
    second = _catalog(roots, first)
    assert {i.id: i.grouping_key for i in second.items.items} == {i.id: i.grouping_key for i in first.items.items}
    a, b, c = (first.by_key[f"pelliot:{number}"].id for number in (2602, 2603, 2604))
    ab_ids = ", ".join(sorted(map(str, (a, b))))
    bc_ids = ", ".join(sorted(map(str, (b, c))))
    assert second.items.pending == {
        a: (f"拟用编号 pelliot:2603 与其他写卷同号，退回原主编号（本轮同号写卷 ID：{ab_ids}）",),
        b: (f"拟用编号 pelliot:2604 与其他写卷同号，退回原主编号（本轮同号写卷 ID：{bc_ids}）",),
    }
    assert not second.items.number_changes
    for owner, old in first.by_id.items():
        current = second.by_id[owner]
        assert (current.serial, current.image_ids, current.identifiers) == (
            old.serial, old.image_ids, old.identifiers,
        )
    reverse = _catalog(roots, first, reverse=True)
    assert reverse.items == second.items
    assert {i.id: i for i in reverse.images.images} == {i.id: i for i in second.images.images}
    assert {i.file.inode: i.id for i in second.images.images} == {
        i.file.inode: i.id for i in first.images.images
    }


def test_image_sets_distinguishable(roots, make_image):
    make_image(roots["data"] / "敦煌003/P2002 版本甲/1.tif", software="Photoshop")
    make_image(roots["data"] / "敦煌004/P2002 版本乙/native.tif")
    snapshot = _catalog(roots)
    item = snapshot.by_key["pelliot:2002"]
    assert len(item.image_ids) == 2
    sources = {str(image.file.relative_path.parent) for image in snapshot.images.images if image.id in item.image_ids}
    assert sources == {"敦煌003/P2002 版本甲", "敦煌004/P2002 版本乙"}
    assert all(owners == {item.id} for owners in snapshot.items.unit_items.values())


@pytest.mark.parametrize("count", [2, 3])
@pytest.mark.parametrize("existing_target", [False, True])
def test_items_renamed_to_one_number_stay_separate(roots, make_image, count, existing_target):
    base = roots["data"] / "敦煌003"
    numbers = list(range(2002, 2002 + count))
    for number in numbers:
        make_image(base / f"P{number}" / "1.tif")
    if existing_target:
        make_image(base / "P2005" / "1.tif")
    make_image(base / "P2010" / "1.tif")  # 无关写卷不应出现在同号说明中。
    first = _catalog(roots)
    for number in numbers:
        (base / f"P{number}").rename(base / f"副本{number} P2005")
    second = _catalog(roots, first)
    changing = {first.by_key[f"pelliot:{number}"].id for number in numbers}
    participants = changing | ({first.by_key["pelliot:2005"].id} if existing_target else set())
    participant_ids = ", ".join(sorted(map(str, participants)))
    assert second.items.pending == {
        owner: (f"拟用编号 pelliot:2005 与其他写卷同号，退回原主编号（本轮同号写卷 ID：{participant_ids}）",)
        for owner in changing
    }
    assert set(second.by_id) == set(first.by_id)
    assert not second.items.number_changes
    for owner, old in first.by_id.items():
        current = second.by_id[owner]
        assert (current.grouping_key, current.serial, current.image_ids, current.identifiers) == (
            old.grouping_key, old.serial, old.image_ids, old.identifiers,
        )
    reverse = _catalog(roots, first, reverse=True)
    assert reverse.items == second.items
    assert {i.id: i for i in reverse.images.images} == {i.id: i for i in second.images.images}
    assert {i.file.inode: i.id for i in second.images.images} == {
        i.file.inode: i.id for i in first.images.images
    }


def test_unkeyed_item_can_gain_number_without_changing_id(roots, make_image):
    directory = roots["data"] / "敦煌003/待定"
    make_image(directory / "1.tif")
    first = _catalog(roots)
    directory.rename(directory.with_name("P2002"))
    second = _catalog(roots, first)
    item = second.by_key["pelliot:2002"]
    assert item.id == first.items.items[0].id and item.serial == first.items.items[0].serial
    assert [(c.before, c.after) for c in second.items.number_changes] == [(None, "pelliot:2002")]
    assert not second.items.pending


def test_new_directory_uses_number_holder_after_rename(roots, make_image):
    base = roots["data"] / "敦煌003"
    directory = base / "P2002"
    make_image(directory / "1.tif")
    first = _catalog(roots)
    directory.rename(base / "P2003")
    make_image(base / "新增 P2003/2.tif")
    second = _catalog(roots, first)
    assert len(second.items.items) == 1
    item = second.by_key["pelliot:2003"]
    assert item.id == first.by_key["pelliot:2002"].id and len(item.image_ids) == 2
    assert not second.items.pending
