"""单元名称的编号解析入口；普通影像文件名不交给此入口。"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from .rules import PELLIOT_RANGES

PART = r"(?:-(?:P)?\d+(?:Pi[èe]ce)?|[A-Za-z](?![A-Za-z]))?"
PELLIOT = re.compile(
    rf"(?<![A-Za-z0-9])(?:Pelliot\s+chinois\s*|P\.?\s*)(?P<number>\d{{4}})(?!\d)(?P<part>{PART})",
    re.IGNORECASE,
)
ADDITIONAL = re.compile(
    rf"\s*\(?\+\s*(?P<raw>(?:P\.?\s*)?(?P<number>\d{{4}})(?!\d)(?P<part>{PART}))\)?",
    re.IGNORECASE,
)
BD = re.compile(r"(?<![A-Za-z0-9])BD(?P<number>\d+)(?P<part>[A-Za-z]*)(?![A-Za-z0-9])", re.IGNORECASE)
SHARER = re.compile(r"(?<![A-Za-z0-9])(?P<prefix>W[AB])\s*(?P<number>\d+)(?!\d)", re.IGNORECASE)
BARE_NUMBER = re.compile(r"(?<![\dA-Za-z.,×x*])\d{4}(?![\dA-Za-z.,×x*])")
UNIT_OR_YEAR = re.compile(r"\s*(?:cm|mm|年|[×x*])", re.IGNORECASE)
ZHIHAO = re.compile(r"([\u4e00-\u9fff])字")
KAIBAO_DIRECTORY = re.compile(r"^敦煌藏經洞\s*\d+")


@dataclass(frozen=True, slots=True)
class Identifier:
    system: Literal["pelliot", "nlc", "sharer", "zhihao", "idp"]
    raw: str
    normalized: str
    key: str | None = None
    parent: str | None = None
    part: str | None = None

    @property
    def compliant(self) -> bool:
        return self.key is not None


@dataclass(frozen=True, slots=True)
class ParsedIdentifiers:
    identifiers: tuple[Identifier, ...]
    suspected: tuple[str, ...]

    @property
    def keys(self) -> frozenset[str]:
        return frozenset(i.key for i in self.identifiers if i.key is not None)


def parse_identifiers(name: str, psb_names: Sequence[str] = ()) -> ParsedIdentifiers:
    """保留原文、规范化各体系，并列出不自动认定的裸四位数。"""
    identifiers, covered = _pelliot_identifiers(name)
    for match in BD.finditer(name):
        identifiers.append(_bd_identifier(match))
        covered.append(match.span())
    for match in SHARER.finditer(name):
        normalized = f"{match['prefix'].upper()} {int(match['number'])}"
        identifiers.append(Identifier("sharer", match.group(), normalized))
        covered.append(match.span())
    if _kaibao_context(name, psb_names):
        identifiers.extend(Identifier("zhihao", m.group(), m[1]) for m in ZHIHAO.finditer(name))
    suspected = tuple(
        m.group() for m in BARE_NUMBER.finditer(name)
        if not any(start <= m.start() < end for start, end in covered)
        and not UNIT_OR_YEAR.match(name, m.end())
        and _in_pelliot_range(int(m.group()))
    )
    return ParsedIdentifiers(tuple(identifiers), suspected)


def _pelliot_identifiers(name: str) -> tuple[list[Identifier], list[tuple[int, int]]]:
    identifiers = []
    covered = []
    for match in PELLIOT.finditer(name):
        if any(start <= match.start() < end for start, end in covered):
            continue
        identifiers.append(_pelliot_identifier(match.group(), match['number'], match['part']))
        covered.append(match.span())
        end = match.end()
        while extra := ADDITIONAL.match(name, end):
            identifiers.append(_pelliot_identifier(extra['raw'], extra['number'], extra['part']))
            covered.append(extra.span())
            end = extra.end()
    return identifiers, covered


def _pelliot_identifier(raw: str, number: str, part: str) -> Identifier:
    n = int(number)
    parent = f"P.{n:04d}"
    component = None
    if part.startswith("-"):
        component = str(int(re.sub(r"Pi[èe]ce$", "", part[1:], flags=re.IGNORECASE).lstrip("Pp")))
        normalized = f"{parent}-{component}"
    elif part:
        component = part.upper()
        normalized = parent + component
    else:
        normalized = parent
    key = f"pelliot:{n}" + (f":{component}" if component else "")
    return Identifier(
        "pelliot", raw, normalized, key if _in_pelliot_range(n) else None,
        parent if component else None, component,
    )


def _in_pelliot_range(number: int) -> bool:
    return any(start <= number <= end for start, end in PELLIOT_RANGES)


def _bd_identifier(match: re.Match) -> Identifier:
    number, suffix = match['number'], match['part']
    parent = "BD" + number
    normalized = parent + suffix.lower()
    compliant = len(number) == 5 and len(suffix) <= 1
    return Identifier(
        "nlc", match.group(), normalized, f"nlc:{normalized}" if compliant else None,
        parent if suffix else None, suffix.lower() or None,
    )


def _kaibao_context(name: str, psb_names: Sequence[str]) -> bool:
    return bool(KAIBAO_DIRECTORY.match(name)) or any(
        "開寶藏" in text or "开宝藏" in text for text in (name, *psb_names)
    )
