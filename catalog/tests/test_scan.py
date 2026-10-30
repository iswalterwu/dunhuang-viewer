import os
import struct

import pytest
import tifffile
from PIL import Image

from dh_catalog.scan import Fact, read_facts, scan


def test_image_inventory_complete(roots, make_image):
    data, backup = roots["data"], roots["backup"]
    names = [
        "敦煌003/P.2800/native.tif", "敦煌003/P.2800/.hidden.tiff",
        "敦煌003/P.2800/big.btf", "188敦煌001/2018年/散放.psb",
        "中国国博馆藏/BD00043a/pages/0001_7x5.jpg",
        "中国国博馆藏/BD00043a/BD00043a_preview.jpg",
    ]
    for name in names:
        make_image(data / name)
    make_image(backup / "敦煌003/P.2800/分段/1.tif")
    inventory = scan(roots)
    assert {(f.root, str(f.relative_path)) for f in inventory.images} == {
        *(('data', name) for name in names), ('backup', "敦煌003/P.2800/分段/1.tif"),
    }
    assert len(inventory.images) == 7
    assert sum(f.hidden for f in inventory.images) == 1
    assert all(f.size > 0 and f.inode > 0 and f.mtime_ns > 0 for f in inventory.images)


def test_excluded_listed_with_reason(roots, make_image):
    data = roots["data"]
    for folder in ("#recycle", "@eaDir", ".pages"):
        make_image(data / "中国国博馆藏/BD00001" / folder / "not_scanned.tif")
    excluded_files = [
        "中国国博馆藏/BD00001/tiles/0_0.jpg", "中国国博馆藏/BD00001/intermediate.npy",
        "A077-敦煌文献目录/book.pdf", "A077-敦煌文献目录/page.png",
        "A077-敦煌文献目录/book.pdf.downloading", "敦煌003/P.2800/not_a_page.jpg",
        "root.tif",
    ]
    for name in excluded_files:
        path = data / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"not imported")
    inventory = scan(roots)
    excluded = {str(e.relative_path): e.reason for e in inventory.excluded}
    assert len(inventory.images) == 0
    assert set(excluded) == {
        *excluded_files,
        *(f"中国国博馆藏/BD00001/{folder}" for folder in ("#recycle", "@eaDir", ".pages")),
    }
    assert all(excluded.values())
    assert "图块" in excluded["中国国博馆藏/BD00001/tiles/0_0.jpg"]
    assert all("not_scanned.tif" not in name for name in excluded)


def test_attachment_inventory(roots):
    names = [
        "敦煌003/P.2800/说明.txt", "敦煌003/分类说明.txt",
        "中国国博馆藏/BD00001/manifest.json", "中国国博馆藏/BD00001/report.json",
        "中国国博馆藏/BD00001/index.json", "A077-敦煌文献目录/仅附件/说明.txt",
    ]
    for name in names:
        p = roots["data"] / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"raw bytes")
    inventory = scan(roots)
    assert {str(f.relative_path) for f in inventory.attachments} == set(names)
    assert not inventory.images


def test_raw_names_verbatim_and_no_source_changes(roots, make_image):
    name = "敦煌003/敦煌遗书 P.2504-1Pièce  Plainte 29,1×45cm---/.原始（全角）.tif"
    path = make_image(roots["data"] / name)
    before = path.read_bytes(), path.stat().st_mtime_ns
    inventory = scan(roots)
    file = inventory.images[0]
    assert str(file.relative_path) == name
    result = read_facts(file, roots["data"])
    assert result.error is None
    assert before == (path.read_bytes(), path.stat().st_mtime_ns)


def test_missing_root_is_not_silently_an_empty_inventory(tmp_path):
    with pytest.raises(FileNotFoundError):
        scan({"data": tmp_path / "absent"})


def test_facts_by_kind(roots, make_image):
    make_image(roots["data"] / "敦煌003/P.2800/1.tif", software="Photoshop", dpi=(180, 180))
    make_image(roots["data"] / "敦煌003/P.2800/.源.psb")
    make_image(roots["data"] / "中国国博馆藏/BD00001/pages/0001_7x5.jpg", dpi=(300, 150))
    results = {f.kind: read_facts(f, roots["data"]) for f in scan(roots).images}
    assert all(r.error is None for r in results.values())
    tiff = results["tiff"].facts
    assert tiff["pixel_size"] == Fact("value", (7, 5))
    assert tiff["channels"] == Fact("value", 3)
    assert tiff["color_mode"] == Fact("value", "RGB")
    assert tiff["bit_depth"] == Fact("value", (8, 8, 8))
    assert tiff["resolution"] == Fact("value", (180.0, 180.0, "INCH"))
    assert tiff["software"] == Fact("value", "Photoshop")
    assert tiff["compression"] == Fact("value", "NONE")
    psb = results["psb"].facts
    assert psb["pixel_size"] == Fact("value", (7, 5))
    assert psb["channels"] == Fact("value", 4)
    assert psb["color_mode"] == Fact("value", "CMYK")
    assert psb["bit_depth"] == Fact("value", 16)
    assert all(psb[k] == Fact("not_applicable") for k in ("resolution", "compression", "software"))
    jpg = results["jpg"].facts
    assert jpg["bit_depth"] == Fact("value", 8)
    assert jpg["channels"] == Fact("value", 3)
    assert jpg["resolution"] == Fact("value", (300.0, 150.0, "INCH"))
    assert jpg["software"] == jpg["compression"] == Fact("not_applicable")


def test_missing_tags_are_not_invented(roots, make_image):
    make_image(roots["data"] / "敦煌003/P.2800/native.tif")
    make_image(roots["data"] / "中国国博馆藏/BD00001/no_dpi_preview.jpg")
    results = {f.kind: read_facts(f, roots["data"]) for f in scan(roots).images}
    assert results["tiff"].facts["software"] == Fact("missing")
    assert results["tiff"].facts["resolution"] == Fact("missing")
    assert results["jpg"].facts["resolution"] == Fact("missing")


def test_exif_without_resolution_does_not_become_72_dpi(roots):
    path = roots["data"] / "中国国博馆藏/BD00001/exif_preview.jpg"
    path.parent.mkdir(parents=True)
    exif = Image.Exif()
    exif[270] = "only a description, no resolution"
    Image.new("RGB", (7, 5)).save(path, exif=exif)
    file = scan(roots).images[0]
    result = read_facts(file, roots["data"])
    assert result.error is None
    assert result.facts["resolution"] == Fact("missing")


def test_jpeg_exif_resolution_preserves_both_axes(roots):
    path = roots["data"] / "中国国博馆藏/BD00001/exif_preview.jpg"
    path.parent.mkdir(parents=True)
    exif = Image.Exif()
    exif[282], exif[283], exif[296] = 100.0, 80.0, 3
    Image.new("RGB", (7, 5)).save(path, exif=exif)
    result = read_facts(scan(roots).images[0], roots["data"])
    assert result.error is None
    assert result.facts["resolution"] == Fact("value", (100.0, 80.0, "CENTIMETER"))


@pytest.mark.parametrize("name,not_applicable", [
    ("敦煌003/P.2800/1.tif", set()),
    ("敦煌003/P.2800/1.psb", {"resolution", "compression", "software"}),
    ("中国国博馆藏/BD00001/bad_preview.jpg", {"compression", "software"}),
])
def test_unreadable_files_keep_not_applicable_and_retry(roots, make_image, name, not_applicable):
    path = roots["data"] / name
    path.parent.mkdir(parents=True)
    path.write_bytes(b"bad header")
    file = scan(roots).images[0]
    first = read_facts(file, roots["data"])
    assert first.error
    assert {k for k, v in first.facts.items() if v.status == "not_applicable"} == not_applicable
    assert all(v.status in {"missing", "not_applicable"} for v in first.facts.values())
    second = read_facts(file, roots["data"], first)
    assert second.error and not second.reused
    make_image(path)
    repaired = read_facts(scan(roots).images[0], roots["data"], first)
    assert repaired.error is None and not repaired.reused
    assert repaired.facts["pixel_size"] == Fact("value", (7, 5))


def test_jpeg_decompression_bomb_is_read_error_and_recovers(roots, make_image):
    path = make_image(roots["data"] / "中国国博馆藏/BD12345/BD12345_preview.jpg", dpi=(180, 180))
    valid = path.read_bytes()
    header = bytearray(valid)
    sof = header.index(b"\xff\xc0")
    # 只改小 JPEG 的 SOF 尺寸，不创建或解码大图，也不修改 Pillow 安全限制。
    header[sof + 5:sof + 9] = struct.pack(">HH", 20000, 20000)
    path.write_bytes(header)
    file, = scan(roots).images
    first = read_facts(file, roots["data"])
    assert first.error and first.error.startswith("DecompressionBombError:")
    assert not first.reused
    assert first.facts == {
        "pixel_size": Fact("missing"), "channels": Fact("missing"),
        "color_mode": Fact("missing"), "bit_depth": Fact("missing"),
        "resolution": Fact("missing"), "compression": Fact("not_applicable"),
        "software": Fact("not_applicable"),
    }
    second = read_facts(file, roots["data"], first)
    assert second.error == first.error and not second.reused
    assert second.facts == first.facts
    path.write_bytes(valid)
    repaired = read_facts(scan(roots).images[0], roots["data"], second)
    assert repaired.error is None and not repaired.reused
    assert repaired.facts == {
        "pixel_size": Fact("value", (7, 5)), "channels": Fact("value", 3),
        "color_mode": Fact("value", "RGB"), "bit_depth": Fact("value", 8),
        "resolution": Fact("value", (180.0, 180.0, "INCH")),
        "compression": Fact("not_applicable"), "software": Fact("not_applicable"),
    }


def test_successful_unchanged_facts_reused_and_change_reread(roots, make_image):
    path = make_image(roots["data"] / "敦煌003/P.2800/1.tif", software="first")
    file = scan(roots).images[0]
    first = read_facts(file, roots["data"])
    second = read_facts(scan(roots).images[0], roots["data"], first)
    assert second.error is None and second.reused
    assert second.facts is first.facts
    make_image(path, software="second version")
    os.utime(path, ns=(path.stat().st_atime_ns, file.mtime_ns + 1_000_000))
    third = read_facts(scan(roots).images[0], roots["data"], second)
    assert not third.reused
    assert third.facts["software"] == Fact("value", "second version")


def test_tiff_only_reads_header_not_pixels(roots, make_image):
    path = make_image(roots["data"] / "敦煌003/P.2800/header_only.tif")
    with tifffile.TiffFile(path) as image:
        pixel_offset = image.pages[0].dataoffsets[0]
    with path.open("r+b") as stream:
        stream.truncate(pixel_offset)
    result = read_facts(scan(roots).images[0], roots["data"])
    assert result.error is None
    assert result.facts["pixel_size"] == Fact("value", (7, 5))


def test_tiff_without_pages_is_a_read_error(roots):
    path = roots["data"] / "敦煌003/P.2800/empty.tif"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"II*\x00" + struct.pack("<I", 0))
    result = read_facts(scan(roots).images[0], roots["data"])
    assert result.error and "没有影像页" in result.error
    assert all(f.status == "missing" for f in result.facts.values())


def test_psb_only_needs_26_byte_header(roots, make_image):
    path = make_image(roots["data"] / "敦煌003/P.2800/source.psb")
    assert path.stat().st_size == struct.calcsize(">4sH6sHIIHH") == 26
    result = read_facts(scan(roots).images[0], roots["data"])
    assert result.error is None
    assert result.facts["bit_depth"] == Fact("value", 16)
