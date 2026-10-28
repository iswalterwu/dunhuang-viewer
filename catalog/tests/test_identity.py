import os
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath
from uuid import UUID

import pytest

from dh_catalog.identity import resolve_images
from dh_catalog.scan import scan

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)


def test_reimport_keeps_ids(roots, make_image):
    make_image(roots["data"] / "敦煌003/P.2800/1.tif")
    first = resolve_images([], scan(roots).images, 1, NOW)
    second = resolve_images(first.images, scan(roots).images, 2, NOW + timedelta(minutes=1))
    assert [i.id for i in first.images] == [i.id for i in second.images]
    assert not second.events
    assert second.images[0].first_seen == 1 and second.images[0].last_seen == 2
    assert first.images[0].last_seen == 1  # 不修改 S0。


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
