import pytest

from dh_catalog.identifiers import parse_identifiers


@pytest.mark.parametrize("raw,normalized,key", [
    ("P2602", "P.2602", "pelliot:2602"),
    ("P.2033", "P.2033", "pelliot:2033"),
    ("P. 0901", "P.0901", None),
    ("p.2731", "P.2731", "pelliot:2731"),
    ("Pelliot chinois 2002", "P.2002", "pelliot:2002"),
    ("P.2504-1Pièce", "P.2504-1", "pelliot:2504:1"),
    ("P.2006-1", "P.2006-1", "pelliot:2006:1"),
    ("P.2222a", "P.2222A", "pelliot:2222:A"),
    ("P2842-P2", "P.2842-2", "pelliot:2842:2"),
])
def test_pelliot_variants_and_suspected(raw, normalized, key):
    result = parse_identifiers(f"敦煌遗书（{raw}） 29,1 × 45 cm---")
    assert len(result.identifiers) == 1
    ident = result.identifiers[0]
    assert ident.raw == raw
    assert ident.normalized == normalized
    assert ident.key == key
    assert not result.suspected
    expected_parent = {
        "P.2504-1Pièce": "P.2504", "P.2006-1": "P.2006",
        "P.2222a": "P.2222", "P2842-P2": "P.2842",
    }.get(raw)
    assert ident.parent == expected_parent


@pytest.mark.parametrize("name,expected,raws", [
    ("P3012+5564", ["P.3012", "P.5564"], ["P3012", "5564"]),
    ("P2661(+3735)", ["P.2661", "P.3735"], ["P2661", "3735"]),
    ("P3012+P.5564", ["P.3012", "P.5564"], ["P3012", "P.5564"]),
    ("P.2002 / P.2800", ["P.2002", "P.2800"], ["P.2002", "P.2800"]),
])
def test_multi_number_shorthand(name, expected, raws):
    result = parse_identifiers(name)
    assert [i.normalized for i in result.identifiers] == expected
    assert [i.raw for i in result.identifiers] == raws
    assert not result.suspected


@pytest.mark.parametrize("number,compliant", [
    (2000, False), (2001, True), (4099, True), (4100, False),
    (4499, False), (4500, True), (5043, True), (5044, False),
    (5257, False), (5521, False), (5522, True), (6038, True), (6039, False), (901, False),
])
def test_ranges_and_doubtful(number, compliant):
    ident = parse_identifiers(f"P.{number:04d}").identifiers[0]
    assert ident.compliant is compliant
    assert ident.raw == f"P.{number:04d}"
    assert (ident.key is not None) is compliant


@pytest.mark.parametrize("name,expected", [
    ("4518(35)", ("4518",)),
    ("開寶藏 2178 源.psb", ("2178",)),
    ("P3012+5564", ()),
    ("12002 20021", ()),
    ("A2002 2002B", ()),
    ("29.2002 29,2002 ×2002 x2002", ()),
    ("2002 cm 2003mm 2004 年 2005 × 2006x", ()),
    ("4100 5257", ()),
    ("2178.psb", ()),  # 紧邻小数点不算独立的四位数。
])
def test_suspected_numbers_exclude_dimensions_and_years(name, expected):
    parsed = parse_identifiers(name)
    assert parsed.suspected == expected
    if expected:
        assert not parsed.identifiers  # 裸四位数不偷偷变成馆藏编号。


@pytest.mark.parametrize("raw,normalized,parent,key", [
    ("BD00001", "BD00001", None, "nlc:BD00001"),
    ("bd00023A", "BD00023a", "BD00023", "nlc:BD00023a"),
    ("BD123", "BD123", None, None),
    ("BD00023ab", "BD00023ab", "BD00023", None),
])
def test_bd_written_form(raw, normalized, parent, key):
    ident = parse_identifiers(raw).identifiers[0]
    assert (ident.raw, ident.normalized, ident.parent, ident.key) == (raw, normalized, parent, key)


@pytest.mark.parametrize("raw,normalized", [("WB15", "WB 15"), ("WB 29", "WB 29"), ("wa9", "WA 9")])
def test_sharer_and_zhihao_systems(raw, normalized):
    ident = parse_identifiers(raw).identifiers[0]
    assert ident.system == "sharer"
    assert ident.raw == raw and ident.normalized == normalized
    assert ident.key is None
    zhihao = parse_identifiers("敦煌藏經洞 2 大般若波邏蜜多經 令字").identifiers[0]
    assert zhihao.system == "zhihao" and zhihao.normalized == "令"
    assert zhihao.raw == "令字" and zhihao.key is None


def test_zhihao_requires_kaibao_context():
    assert not parse_identifiers("P.2002 小字法华经").identifiers[1:]
    parsed = parse_identifiers("存字 經", psb_names=("開寶藏零件.psb",))
    assert [(i.system, i.raw) for i in parsed.identifiers] == [("zhihao", "存字")]


def test_primary_only_compliant():
    result = parse_identifiers("P.2002 P.0901 WB 29 BD00001")
    assert result.keys == {"pelliot:2002", "nlc:BD00001"}
    assert not parse_identifiers("WB 29").keys
    assert not parse_identifiers("P.5257").keys
    assert not parse_identifiers("no identifier").keys
