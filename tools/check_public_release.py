#!/usr/bin/env python3
"""Scan tracked/index/pending text or every object reachable from explicit refs.

Private JSON schema: {"version": 1, "replacements": [{"category": "identity",
"private": "synthetic-person@example.invalid", "public": "contributors@example.invalid"}]}.
Rules are literal, case-sensitive and longest-first; only classified values belong
in this file. Optional candidate aliases use {"full_to_alias": {full_oid: alias}}.
Both inputs must be outside the scanned repository. No matched text, object IDs,
private input paths or Git diagnostics are printed. Exit: 0 clean, 1 findings,
2 invalid input/operation. This is not proof against unknown secret formats.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import subprocess
import sys

CATEGORIES = frozenset({
    "identity", "endpoint", "network", "host_path", "workstation_path",
    "device", "acquisition", "operation", "quota", "credential", "candidate",
})
PUBLIC_NAME = "Project Contributors"
PUBLIC_EMAIL = "contributors@example.invalid"
BRANCHES = ("refs/heads/main", "refs/heads/feat/catalog-foundation")
# Reserved documentation addresses and role paths are deliberately not blocked.
SHAPES = {
    "private_network_shape": re.compile(
        r"(?<![\d.])(?:192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
        r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
        r"|100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3})(?![\d.])"
    ),
    "personal_home_shape": re.compile(
        r"(?i)(?:[a-z]:[/\\]Users[/\\]|/home/|/Users/)[\w.-]+"
    ),
    "host_storage_shape": re.compile(r"/volume\d+/[^\s\"'`<>]+"),
    "private_key_shape": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "archive_reference": re.compile(r"\bhandoff/(?!README\.md\b)[\w./-]+"),
}


class ReleaseError(Exception):
    """Deliberately value-free error, safe for the public console."""


class QuietParser(argparse.ArgumentParser):
    def error(self, message):
        raise ReleaseError("invalid_arguments")


def git(repo: Path, *args: str, data: bytes | None = None) -> bytes:
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0")
    process = subprocess.run(
        ["git", "-C", str(repo), *args], input=data, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, env=env, check=False,
    )
    if process.returncode:
        raise ReleaseError("git_operation_failed")
    return process.stdout


def repository_root(path: Path) -> Path:
    bare = git(path, "rev-parse", "--is-bare-repository").strip() == b"true"
    flag = "--absolute-git-dir" if bare else "--show-toplevel"
    return Path(git(path, "rev-parse", flag).decode("utf-8").strip()).resolve()


def external_file(path: Path, repo: Path) -> Path:
    path = path.resolve()
    if path.is_relative_to(repo.resolve()) or not path.is_file():
        raise ReleaseError("private_input_must_be_external")
    return path


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValueError):
        raise ReleaseError("invalid_private_json") from None


class Rules:
    def __init__(self, entries=(), aliases=None):
        self.entries = sorted(entries, key=lambda row: len(row[1]), reverse=True)
        self.aliases = aliases or {}
        self.alias_tokens = {}
        for oid, alias in self.aliases.items():
            for size in range(7, len(oid) + 1):
                token = oid[:size]
                if token in self.alias_tokens and self.alias_tokens[token] != alias:
                    raise ReleaseError("ambiguous_candidate_alias")
                self.alias_tokens[token] = alias
        self.alias_pattern = (
            re.compile(r"(?:(?<![0-9a-f])|(?<=HEAD))(?:" + "|".join(
                sorted(self.alias_tokens, key=len, reverse=True)
            ) + r")(?![0-9a-f])", re.IGNORECASE)
            if self.alias_tokens else None
        )
        self.literal_pattern = (
            re.compile("|".join(re.escape(row[1]) for row in self.entries))
            if self.entries else None
        )
        self.replacement_by_value = {row[1]: row[2] for row in self.entries}

    def transform(self, data: bytes) -> bytes:
        text, status = decode_text(data)
        if status != "text":
            return data
        if self.literal_pattern:
            text = self.literal_pattern.sub(
                lambda match: self.replacement_by_value[match[0]], text
            )
        if self.alias_pattern:
            text = self.alias_pattern.sub(
                lambda match: self.alias_tokens[match[0].lower()], text
            )
        # Preserve encoding/BOM and bytes exactly if nothing changed.
        old, _ = decode_text(data)
        if text == old:
            return data
        if data.startswith((b"\xff\xfe", b"\xfe\xff")):
            encoding = "utf-16-le" if data.startswith(b"\xff\xfe") else "utf-16-be"
            return data[:2] + text.encode(encoding)
        return (b"\xef\xbb\xbf" if data.startswith(b"\xef\xbb\xbf") else b"") + text.encode("utf-8")

    def matches(self, text: str) -> Counter:
        found = Counter()
        for category, private, _ in self.entries:
            count = text.count(private)
            if count:
                found[category] += count
        if self.alias_pattern:
            count = len(self.alias_pattern.findall(text))
            if count:
                found["candidate"] += count
        for category, pattern in SHAPES.items():
            count = len(pattern.findall(text))
            if count:
                found[category] += count
        return found


def load_rules(repo: Path, private_rules: Path | None, aliases: Path | None = None) -> Rules:
    entries = []
    if private_rules:
        document = read_json(external_file(private_rules, repo))
        if not isinstance(document, dict) or document.get("version") != 1 or not isinstance(document.get("replacements"), list):
            raise ReleaseError("invalid_rule_schema")
        seen = set()
        for row in document["replacements"]:
            if not isinstance(row, dict):
                raise ReleaseError("invalid_rule_schema")
            category, private, public = (row.get(key) for key in ("category", "private", "public"))
            if (not isinstance(category, str) or category not in CATEGORIES or not isinstance(private, str) or not private
                    or not isinstance(public, str) or private == public or private in seen):
                raise ReleaseError("invalid_rule_schema")
            seen.add(private)
            entries.append((category, private, public))
    mapping = {}
    if aliases:
        document = read_json(external_file(aliases, repo))
        mapping = document.get("full_to_alias") if isinstance(document, dict) else None
        if not isinstance(mapping, dict) or any(
            not re.fullmatch(r"[0-9a-f]{40}", oid)
            or not isinstance(alias, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", alias)
            for oid, alias in mapping.items()
        ):
            raise ReleaseError("invalid_alias_schema")
    return Rules(entries, mapping)


def decode_text(data: bytes) -> tuple[str, str]:
    try:
        if data.startswith((b"\xff\xfe", b"\xfe\xff")):
            return data.decode("utf-16"), "text"
        if b"\0" in data:
            return "", "binary-excluded"
        return data.decode("utf-8-sig"), "text"
    except UnicodeError:
        return "", "unrecognized-format"


def objects(repo: Path, oids):
    """Git's size-framed batch output, not quoted paths or a fast-import stream."""
    oids = list(oids)
    if not oids:
        return
    raw = git(repo, "cat-file", "--batch", data=("\n".join(oids) + "\n").encode("ascii"))
    offset = 0
    for oid in oids:
        end = raw.index(b"\n", offset)
        header = raw[offset:end].split()
        if len(header) != 3 or header[0].decode("ascii") != oid:
            raise ReleaseError("invalid_git_object")
        size = int(header[2])
        offset = end + 1
        yield oid, header[1].decode("ascii"), raw[offset:offset + size]
        offset += size + 1


def tree_entries(repo: Path, ref: str):
    for record in git(repo, "ls-tree", "-rz", "--full-tree", ref).split(b"\0"):
        if record:
            meta, path = record.split(b"\t", 1)
            mode, kind, oid = meta.decode("ascii").split()
            yield mode, kind, oid, path


def old_archive(path: bytes) -> bool:
    return path.startswith(b"handoff/") and path != b"handoff/README.md"


class Scan:
    def __init__(self, rules: Rules):
        self.rules = rules
        self.findings = []
        self.coverage = []
        self.counts = Counter()

    def add(self, location: str, category: str, count: int = 1):
        self.findings.append({"location": location, "category": category, "count": count})

    def path(self, path: bytes, alias: str) -> str:
        text = path.decode("utf-8", errors="replace")
        hits = self.rules.matches(text)
        if old_archive(path):
            hits["old_archive"] += 1
        for category, count in hits.items():
            self.add(alias, category, count)
        # Never expose a private path, even when it occurs only in a filename.
        return alias if hits else text

    def text(self, data: bytes, location: str):
        text, status = decode_text(data)
        self.coverage.append({"location": location, "status": status})
        self.counts[status] += 1
        if status == "unrecognized-format":
            self.add(location, status)
        if status == "text":
            for category, count in self.rules.matches(text).items():
                self.add(location, category, count)

    def report(self):
        return {"status": "findings" if self.findings else "clean",
                "counts": dict(self.counts), "findings": self.findings,
                "coverage": self.coverage,
                "limits": "Selected scope only; binary exclusions and unknown formats need human review. Not a guarantee against unknown secrets or retained third-party copies."}


def scan_worktree(repo: Path, rules: Rules) -> dict:
    scan = Scan(rules)
    indexed = []
    for record in git(repo, "ls-files", "--stage", "-z").split(b"\0"):
        if record:
            meta, path = record.split(b"\t", 1)
            _, oid, stage = meta.decode("ascii").split()
            if stage != "0":
                raise ReleaseError("unmerged_index")
            indexed.append((oid, path))
    blobs = {oid: data for oid, _, data in objects(repo, dict.fromkeys(oid for oid, _ in indexed))}
    for number, (oid, path) in enumerate(indexed, 1):
        label = scan.path(path, f"index-path-{number}")
        scan.text(blobs[oid], "index:" + label)
    paths = git(repo, "ls-files", "--cached", "--others", "--exclude-standard", "-z").split(b"\0")
    for number, path in enumerate(dict.fromkeys(p for p in paths if p), 1):
        label = scan.path(path, f"worktree-path-{number}")
        target = repo / path.decode("utf-8")
        if target.is_symlink():
            data = os.readlink(target).encode("utf-8")
        elif target.is_file():
            data = target.read_bytes()
        elif not target.exists():
            scan.coverage.append({"location": "worktree:" + label, "status": "deleted"})
            continue
        else:
            scan.add("worktree:" + label, "unrecognized-format")
            continue
        scan.text(data, "worktree:" + label)
    return scan.report()


def resolve_refs(repo: Path, refs) -> list[str]:
    if not refs or any(not ref.startswith("refs/") for ref in refs):
        raise ReleaseError("explicit_full_refs_required")
    return [git(repo, "rev-parse", "--verify", ref + "^{commit}").decode("ascii").strip() for ref in refs]


def scan_history(repo: Path, refs, rules: Rules) -> dict:
    tips = resolve_refs(repo, refs)
    scan = Scan(rules)
    oids = git(repo, "rev-list", "--objects", "--no-object-names", *tips, "--").decode("ascii").splitlines()
    trees = set()
    for number, (oid, kind, data) in enumerate(objects(repo, oids), 1):
        label = f"history-{kind}-{number}"
        scan.counts[kind] += 1
        if kind == "blob":
            scan.text(data, label)
        elif kind == "commit":
            header, message = data.split(b"\n\n", 1)
            scan.text(message, label + ":message")
            for line in header.splitlines():
                if line.startswith(b"tree "):
                    trees.add(line[5:].decode("ascii"))
                elif line.startswith((b"author ", b"committer ")):
                    role, identity = line.split(b" ", 1)
                    identity_label = label + ":" + role.decode("ascii")
                    scan.text(identity, identity_label)
                    if not re.fullmatch(
                        re.escape(f"{PUBLIC_NAME} <{PUBLIC_EMAIL}>").encode("ascii") + rb" -?\d+ \+0000", identity
                    ):
                        scan.add(identity_label, "nonpublic_identity")
    for number, tree in enumerate(sorted(trees), 1):
        for entry_number, (_, _, _, path) in enumerate(tree_entries(repo, tree), 1):
            scan.path(path, f"history-tree-{number}-path-{entry_number}")
    return scan.report()


def main(argv=None) -> int:
    parser = QuietParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--private-rules", type=Path)
    parser.add_argument("--candidate-aliases", type=Path)
    parser.add_argument("--refs", nargs="+", help="Full refs; scan ALL reachable blobs/messages/identities, instead of index + worktree")
    try:
        args = parser.parse_args(argv)
        repo = repository_root(args.repo.resolve())
        rules = load_rules(repo, args.private_rules, args.candidate_aliases)
        report = scan_history(repo, args.refs, rules) if args.refs else scan_worktree(repo, rules)
        print(json.dumps(report, ensure_ascii=True, indent=2))
        return int(report["status"] != "clean")
    except (ReleaseError, OSError, UnicodeError, ValueError) as error:
        category = str(error) if isinstance(error, ReleaseError) else "operation_failed"
        print(json.dumps({"status": "error", "category": category}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
