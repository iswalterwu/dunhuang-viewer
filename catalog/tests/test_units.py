import pytest

from dh_catalog.scan import scan
from dh_catalog.units import build_units


def test_subdirs(roots, make_image):
    parent = roots["data"] / "敦煌003/P.2002"
    for name in ("main.tif", "分段/1.tif", "HD/1.tif", "P.2002HD/1.tif", "P.2003/1.tif"):
        make_image(parent / name)
    result = build_units(scan(roots))
    assert len(result.units) == 2
    units = {u.name: u for u in result.units}
    assert units["P.2002"].parsed.keys == {"pelliot:2002"}
    assert units["P.2003"].parsed.keys == {"pelliot:2003"}
    roles = {str(i.file.relative_path): i.role for i in units["P.2002"].images}
    assert roles == {
        "敦煌003/P.2002/main.tif": "单幅整卷",
        "敦煌003/P.2002/分段/1.tif": "分段",
        "敦煌003/P.2002/HD/1.tif": "另一版本",
        "敦煌003/P.2002/P.2002HD/1.tif": "另一版本",
    }
    unknown = [i for i in result.issues if i.category == "词表外子目录"]
    assert [str(i.relative_path) for i in unknown] == ["敦煌003/P.2002/P.2003"]


@pytest.mark.parametrize("name", ["分", "切片", "片", "斷巻分段", "全巻分段", "全巻分", "全卷分", "寫 1巻分段", "左裁"])
def test_segment_vocabulary(roots, make_image, name):
    make_image(roots["data"] / "敦煌003/P.2002" / name / "1.tif")
    result = build_units(scan(roots))
    assert len(result.units) == 1
    assert result.units[0].images[0].role == "分段"
    assert not any(i.category == "词表外子目录" for i in result.issues)


def test_nlc_pages_preview_and_tiles(roots, make_image):
    directory = roots["data"] / "中国国博馆藏/BD00043a"
    make_image(directory / "pages/0001_7x5.jpg")
    make_image(directory / "BD00043a_preview.jpg")
    tiles = directory / "tiles/0_0.jpg"
    tiles.parent.mkdir()
    tiles.write_bytes(b"excluded tile")
    result = build_units(scan(roots))
    assert len(result.units) == 1
    unit = result.units[0]
    assert unit.parsed.keys == {"nlc:BD00043a"}
    assert {i.role for i in unit.images} == {"页图", "另一版本"}
    assert not any(i.category == "词表外子目录" for i in result.issues)
    assert any(str(e.relative_path).endswith("tiles") for e in result.excluded)


def test_loose_files(roots, make_image):
    batch = roots["data"] / "188敦煌001/2018年"
    make_image(batch / "温泉铭（P.4508）.tif")
    make_image(batch / "原始 2178 源.psb")
    make_image(roots["data"] / "敦煌003/P.2800/2660-1.tif")
    result = build_units(scan(roots))
    assert len(result.units) == 3
    units = {u.name: u for u in result.units}
    assert units["温泉铭（P.4508）.tif"].parsed.keys == {"pelliot:4508"}
    assert units["原始 2178 源.psb"].parsed.suspected == ("2178",)
    assert units["P.2800"].parsed.keys == {"pelliot:2800"}
    assert not units["P.2800"].parsed.suspected  # 普通文件名 2660-1.tif 不参与编号解析。


def test_attachments_and_attachment_only_directories(roots, make_image):
    directory = roots["data"] / "敦煌003/P.2002"
    make_image(directory / "main.tif")
    names = ["P.2002HD/说明.txt", "仅说明的子目录/说明.txt"]
    for name in names:
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"verbatim attachment")
    lonely = roots["data"] / "敦煌003/只有附件/说明.txt"
    lonely.parent.mkdir()
    lonely.write_bytes(b"no images")
    top = roots["data"] / "敦煌003/分类说明.txt"
    top.write_bytes(b"category attachment")
    result = build_units(scan(roots))
    assert len(result.units) == 1
    assert {str(f.relative_path) for f in result.units[0].attachments} == {
        "敦煌003/P.2002/" + name for name in names
    }
    assert {f.relative_path.name for f in result.unassigned_attachments} == {"说明.txt", "分类说明.txt"}
    assert [str(i.relative_path) for i in result.issues if i.category == "缺少影像"] == ["敦煌003/只有附件"]
    assert not any(i.category == "词表外子目录" for i in result.issues)


def test_merge_suggestions_only(roots, make_image):
    for name in ("WB 29 A", "WB29 B", "經文 上部", "經文 下部", "敦煌藏經洞 1 令字", "敦煌藏經洞 2 令字"):
        make_image(roots["data"] / "188敦煌001/2018年" / name / "1.tif")
    result = build_units(scan(roots))
    assert len(result.units) == 6
    assert all(not u.parsed.keys for u in result.units)
    pairs = {(s.left.rsplit("/", 1)[-1], s.right.rsplit("/", 1)[-1]) for s in result.suggestions}
    assert pairs == {("WB 29 A", "WB29 B"), ("經文 上部", "經文 下部"), ("敦煌藏經洞 1 令字", "敦煌藏經洞 2 令字")}


def test_paper_back_pair_and_compliant_units_not_suggested(roots, make_image):
    for name in ("同名", "同名紙背", "P.2002 上部", "P.2002 下部"):
        make_image(roots["data"] / "敦煌003" / name / "1.tif")
    result = build_units(scan(roots))
    assert len(result.units) == 4  # 这里只划单元，按号归并由 identity 完成。
    assert len(result.suggestions) == 1
    assert "同名" in result.suggestions[0].left
    assert "同名紙背" in result.suggestions[0].right


def test_backup_fragments_mapped(roots, make_image):
    make_image(roots["data"] / "敦煌003/P.2002/main.tif")
    make_image(roots["backup"] / "敦煌003/P.2002/old.tif")
    make_image(roots["backup"] / "敦煌003/P.2002/分段/1.tif")
    make_image(roots["backup"] / "敦煌003/P.2003/分段/2.tif")
    result = build_units(scan(roots))
    assert len(result.units) == 2
    units = {u.name: u for u in result.units}
    assert units["P.2002"].key == "data:敦煌003/P.2002"
    assert {i.role for i in units["P.2002"].images} == {"单幅整卷", "已迁出的分片"}
    assert len(units["P.2002"].images) == 3
    assert units["P.2003"].key == "backup:敦煌003/P.2003"
    assert units["P.2003"].images[0].role == "已迁出的分片"
    assert [str(i.relative_path) for i in result.issues if i.category == "备份分片对不上"] == ["敦煌003/P.2003"]
    assert not (roots["data"] / "敦煌003/P.2002/分段").exists()
    assert not (roots["data"] / "敦煌003/P.2003").exists()


def test_backup_can_supply_images_for_original_attachment_only_directory(roots, make_image):
    directory = roots["data"] / "敦煌003/P.2002"
    directory.mkdir(parents=True)
    (directory / "说明.txt").write_bytes(b"preserve me")
    make_image(roots["backup"] / "敦煌003/P.2002/分段/1.tif")
    result = build_units(scan(roots))
    assert len(result.units) == 1
    assert len(result.units[0].attachments) == 1
    assert not any(i.category in {"缺少影像", "备份分片对不上"} for i in result.issues)


def test_new_category_with_only_references(roots):
    path = roots["data"] / "A077-敦煌文献目录/参考书/说明.txt"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"raw reference description")
    (path.parent / "book.pdf").write_bytes(b"not imported")
    result = build_units(scan(roots))
    assert result.new_categories == ["A077-敦煌文献目录"]
    assert not result.units
    assert len(result.unassigned_attachments) == 1
    assert any(i.category == "缺少影像" for i in result.issues)
    assert any(e.relative_path.name == "book.pdf" for e in result.excluded)


def test_hidden_mixed_only_flagged_when_non_hidden_image_in_same_directory(roots, make_image):
    for name in (".hidden.tif", "main.tif", "HD/.only_hidden.tif", "合并长卷.tif", "合并长卷.psb"):
        make_image(roots["data"] / "敦煌003/P.2002" / name)
    result = build_units(scan(roots))
    flagged = [i.relative_path.name for i in result.issues if i.category == "隐藏文件与非隐藏影像同目录（待确认）"]
    assert flagged == [".hidden.tif"]
    roles = {i.file.relative_path.name: i.role for i in result.units[0].images}
    assert roles["合并长卷.psb"] == "PSB 源文件"
    assert roles["合并长卷.tif"] == "合并长卷"
    assert roles["main.tif"] == "分段"  # 与 .hidden.tif 同属两个普通 TIFF。


def test_zhihao_context_can_come_from_same_directory_psb(roots, make_image):
    directory = roots["data"] / "188敦煌001/2018年/令字 經"
    make_image(directory / "1.tif")
    make_image(directory / "開寶藏零件.psb")
    result = build_units(scan(roots))
    assert [(i.system, i.normalized) for i in result.units[0].parsed.identifiers] == [("zhihao", "令")]
