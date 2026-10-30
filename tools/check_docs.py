"""Check public Markdown consistency; derived from the former handoff checker.

Run: python -I -X utf8 tools/check_docs.py .
Only category, repository-relative file and count are printed. No matched text,
addresses, private paths or exception messages are emitted. This is a document
check, not an exhaustive privacy audit or a network/external-link validator.
"""
from __future__ import annotations

from collections import Counter
import ipaddress
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    problems: Counter[tuple[str, str]] = Counter()
    try:
        names = subprocess.check_output(
            ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others",
             "--exclude-standard", "--", "*.md"], stderr=subprocess.DEVNULL,
        ).decode("utf-8").split("\0")
    except (OSError, subprocess.CalledProcessError, UnicodeError):
        print("inventory-error\t.\t1")
        return 1
    texts = {}
    for name in sorted(set(filter(None, names))):
        path = root / name
        # Unstaged authorized archive removals remain in the Git index.
        if not path.exists():
            continue
        try:
            raw = path.read_bytes()
            texts[name] = raw.decode("utf-8")
        except (OSError, UnicodeError):
            problems["unreadable-markdown", name] += 1
            continue
        if raw.startswith(b"\xef\xbb\xbf") or b"\r\n" in raw:
            problems["encoding-or-newline", name] += 1
    check_ids(texts, problems)
    check_sections(texts, problems)
    for name, text in texts.items():
        check_markdown(root, name, text, texts, problems)
    for (category, name), count in sorted(problems.items()):
        print(f"{category}\t{name}\t{count}")
    print(f"markdown-files\t.\t{len(texts)}")
    print(f"problems\t.\t{sum(problems.values())}")
    return int(bool(problems))


def check_ids(texts: dict[str, str], problems: Counter) -> None:
    plan = texts.get("docs/plan.md", "")
    defined = set(re.findall(r"^\| (PD-\d{2}|RK-\d{2}|KI-\d{2}|Q-\d{2}) \|", plan, re.M))
    adrs: Counter[str] = Counter()
    for name, text in texts.items():
        if name.startswith("docs/decisions/2"):
            match = re.match(r"# (D-\d{3}) ", text)
            if match:
                adrs[match[1]] += 1
            else:
                problems["adr-heading", name] += 1
    problems.update({("duplicate-adr", "docs/decisions"): sum(n - 1 for n in adrs.values())})
    # Remove zero counters so an entirely clean run returns zero.
    if not problems["duplicate-adr", "docs/decisions"]:
        del problems["duplicate-adr", "docs/decisions"]
    for name, text in texts.items():
        if not name.startswith("specs/catalog-foundation/"):
            missing = set(re.findall(r"\b(?:PD|RK|KI|Q)-\d{2}\b", text)) - defined
            if missing:
                problems["undefined-project-id", name] += len(missing)
        missing = set(re.findall(r"D-\d{3}", text)) - set(adrs)
        if missing:
            problems["undefined-adr", name] += len(missing)
    for feature, expected in (("catalog-foundation", (13, 58)), ("public-release-privacy", (7, 25))):
        base = f"specs/{feature}/"
        spec = texts.get(base + "spec.md", "")
        fplan = texts.get(base + "plan.md", "")
        reqs = re.findall(r"^### (R-\d{3}) ", spec, re.M)
        acs = re.findall(r"- \[[ x]\] (AC-\d{3}-\d+)\b", spec)
        if (len(reqs), len(acs)) != expected or len(set(acs)) != len(acs):
            problems["requirement-count", base + "spec.md"] += 1
        for req in reqs:
            ns = [int(ac.rsplit("-", 1)[1]) for ac in acs if ac.startswith("AC-" + req[2:] + "-")]
            if not ns or ns != list(range(1, len(ns) + 1)):
                problems["ac-sequence", base + "spec.md"] += 1
        plan_acs = re.findall(r"^\| (AC-\d{3}-\d+) \|", fplan, re.M)
        if set(acs) != set(plan_acs) or len(set(plan_acs)) != len(plan_acs):
            problems["plan-ac-coverage", base + "plan.md"] += 1
        for suffix in ("spec.md", "plan.md", "checklist.md"):
            refs = set(re.findall(r"AC-\d{3}-\d+", texts.get(base + suffix, "")))
            if refs - set(acs):
                problems["undefined-ac", base + suffix] += len(refs - set(acs))
        qs = re.findall(r"^\| (Q-\d{3}) \|", spec, re.M)
        seq = [int(q[2:]) for q in qs]
        refs = set(re.findall(r"\bQ-\d{3}\b", spec + fplan))
        if seq != list(range(1, len(qs) + 1)) or refs - set(qs):
            problems["clarify-sequence-or-reference", base + "spec.md"] += 1


def check_sections(texts: dict[str, str], problems: Counter) -> None:
    headings = {
        name: set(re.findall(r"^#{2,4} (\d+(?:\.\d+)*)\.? ", text, re.M))
        | set(re.findall(r"^\*\*(\d+\.\d+\.\d+) ", text, re.M))
        for name, text in texts.items()
    }
    for name, raw in texts.items():
        # Historical reviewer extracts are not rewritten as current navigation.
        text = re.sub(r"<details>.*?</details>", "", raw, flags=re.S)
        in_feature = name.startswith("specs/catalog-foundation/")
        for m in re.finditer(r"(docs/plan\.md|plan\.md|architecture\.md|designUI\.md|AGENTS\.md|spec(?:\.md)?) §(\d+(?:\.\d+)*)", text):
            target, sec = m.groups()
            if target.startswith("spec"):
                feature = name.split("/")[1] if name.startswith("specs/") and name.count("/") > 1 else "catalog-foundation"
                ok = sec.split(".")[0] in headings.get(f"specs/{feature}/spec.md", set())
            elif target == "plan.md" and in_feature and not name.endswith("/spec.md"):
                ok = sec in headings.get("docs/plan.md", set()) | headings.get("specs/catalog-foundation/plan.md", set())
            else:
                target = target if target.startswith("docs/") or target == "AGENTS.md" else "docs/" + target
                ok = sec in headings.get(target, set())
            if not ok:
                problems["missing-section", name] += 1
        if name in ("specs/catalog-foundation/plan.md", "specs/catalog-foundation/checklist.md"):
            for m in re.finditer(r"(?<![\w./])§(\d+\.\d+(?:\.\d+)?)(?!\S*\s*(?:Q-|术语))", text):
                prefix = text[max(0, m.start() - 20):m.start()]
                if re.search(r"(plan\.md|architecture\.md|designUI\.md|AGENTS\.md|spec(?:\.md)?) $", prefix):
                    continue
                if m[1] not in headings.get("specs/catalog-foundation/plan.md", set()):
                    problems["missing-local-section", name] += 1


def anchors(text: str) -> set[str]:
    result = set(re.findall(r'<a\s+(?:id|name)=[\"\']([^\"\']+)', text))
    seen: Counter[str] = Counter()
    for title in re.findall(r"^#{1,6}\s+(.+?)\s*#*\s*$", text, re.M):
        slug = re.sub(r"[^\w\-\s]", "", title.lower()).replace(" ", "-")
        suffix = f"-{seen[slug]}" if seen[slug] else ""
        result.add(slug + suffix)
        seen[slug] += 1
    return result


def check_markdown(root: Path, name: str, text: str, texts: dict[str, str], problems: Counter) -> None:
    fence = None
    columns = None
    prose = []
    for line in text.splitlines():
        m = re.match(r"^\s*(`{3,}|~{3,})", line)
        if m:
            marker = m[1]
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
            columns = None
            continue
        if fence:
            continue
        prose.append(line)
        if line.startswith("|"):
            n = line.count("|") - line.count(r"\|")
            if columns is not None and n != columns:
                problems["table-columns", name] += 1
            columns = n
        else:
            columns = None
    if fence:
        problems["unclosed-fence", name] += 1
    for target in re.findall(r"\[[^\]\n]*\]\(([^\s)]+)(?:\s+\"[^\"]*\")?\)", "\n".join(prose)):
        try:
            parsed = urlsplit(target.strip("<>"))
        except ValueError:
            problems["invalid-link", name] += 1
            continue
        if parsed.scheme or parsed.netloc:
            continue
        path = (root / name).parent / unquote(parsed.path) if parsed.path else root / name
        try:
            relative = path.resolve().relative_to(root).as_posix()
        except ValueError:
            problems["link-outside-repository", name] += 1
            continue
        if not path.exists():
            problems["missing-link", name] += 1
        elif parsed.fragment and relative in texts and unquote(parsed.fragment) not in anchors(texts[relative]):
            problems["missing-anchor", name] += 1
    if re.search(r"(?:\.\./)*handoff/\d{4}-\d{2}-\d{2}(?:/|\b)", text):
        problems["obsolete-archive-reference", name] += 1
    for value in re.findall(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])", text):
        try:
            ip = ipaddress.ip_address(value)
        except ValueError:
            continue
        examples = (ipaddress.ip_network("192.0.2.0/24"), ipaddress.ip_network("198.51.100.0/24"), ipaddress.ip_network("203.0.113.0/24"))
        if not ip.is_loopback and not ip.is_unspecified and not any(ip in network for network in examples):
            problems["address-review-required", name] += 1


if __name__ == "__main__":
    raise SystemExit(main())
