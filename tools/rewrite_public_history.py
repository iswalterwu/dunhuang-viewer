#!/usr/bin/env python3
"""Offline, native filter-branch rehearsal for exactly main and the feature branch.

rewrite requires a local committed source, a NEW independent bare output and a
NEW external private-result directory. Neither source refs nor remotes change.
Private rules/aliases follow check_public_release.py. The feature tip must already
be clean: any tree/mode change is a failure, not an implicit tip repair. All old
OIDs, mappings, logs, rules and integrity manifests stay in the private directory.
A failed output is NOT publishable. No network, push or source-branch switching is
implemented. Review and the human release gate remain mandatory.

plan reads two previously recorded exact leases (JSON mapping full branch refs to
40-character OIDs), checks refs/rewritten/main and refs/rewritten/feat/catalog-foundation,
and writes a private JSON argv. Console output is a redacted command template.
It NEVER refreshes leases, contacts a remote, or executes the generated command.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

# Direct script execution also works with Python -I; no application import/deps.
# Even a plain CLI invocation must not create bytecode files in its source tree.
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_public_release import (  # noqa: E402
    BRANCHES, PUBLIC_EMAIL, PUBLIC_NAME, QuietParser, ReleaseError, Rules,
    external_file, git, load_rules, objects, old_archive, read_json,
    repository_root, resolve_refs, scan_history, tree_entries,
)

REWRITTEN = tuple(ref.replace("refs/heads/", "refs/rewritten/", 1) for ref in BRANCHES)


def save_json(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=True, indent=2) + "\n", encoding="utf-8", newline="\n")


def is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", ancestor, descendant],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if result.returncode not in (0, 1):
        raise ReleaseError("ancestry_check_failed")
    return result.returncode == 0


def validate_destinations(source: Path, output: Path, private_dir: Path):
    if not source.is_dir() or output.exists() or private_dir.exists():
        raise ReleaseError("new_external_destinations_required")
    paths = (source, output, private_dir)
    if any(a.is_relative_to(b) for a in paths for b in paths if a != b) or len(set(paths)) != 3:
        raise ReleaseError("independent_destinations_required")
    resolve_refs(source, BRANCHES)
    # A committed snapshot is the only input; never silently ignore dirty edits.
    bare = git(source, "rev-parse", "--is-bare-repository").strip() == b"true"
    if not bare and git(source, "status", "--porcelain", "--untracked-files=normal"):
        raise ReleaseError("source_must_be_committed_and_clean")
    if git(source, "rev-parse", "--is-shallow-repository").strip() != b"false":
        raise ReleaseError("complete_source_required")


def expanded_aliases(source: Path, rules: Rules) -> dict:
    mapping = dict(rules.aliases)
    commits = git(source, "rev-list", "--reverse", "--topo-order", *BRANCHES, "--").decode("ascii").splitlines()
    number = 1
    for oid in commits:
        if oid not in mapping:
            while f"Candidate-extension-{number:03d}" in mapping.values():
                number += 1
            mapping[oid] = f"Candidate-extension-{number:03d}"
            number += 1
    return mapping


def tip_check(repo: Path, rules: Rules) -> dict:
    """Fail before filtering if the accepted feature tip would need any repair."""
    entries = list(tree_entries(repo, BRANCHES[1]))
    data_by_oid = {oid: data for oid, _, data in objects(repo, dict.fromkeys(entry[2] for entry in entries))}
    from check_public_release import Scan
    scan = Scan(rules)
    for number, (_, kind, oid, path) in enumerate(entries, 1):
        label = scan.path(path, f"feature-tip-path-{number}")
        if kind != "blob":
            scan.add(label, "unsupported_tree_entry")
            continue
        data = data_by_oid[oid]
        scan.text(data, label)
        if rules.transform(data) != data:
            scan.add(label, "feature_tip_would_change")
    return scan.report()


def manifest(repo: Path, ref: str) -> list[dict]:
    entries = list(tree_entries(repo, ref))
    contents = {oid: data for oid, _, data in objects(repo, dict.fromkeys(row[2] for row in entries))}
    return [{"path": path.decode("utf-8"), "mode": mode,
             "sha256": hashlib.sha256(contents[oid]).hexdigest()}
            for mode, _, oid, path in entries]


def rewrite(args) -> dict:
    source = repository_root(args.source.resolve())
    output, private_dir = args.output.resolve(), args.private_dir.resolve()
    validate_destinations(source, output, private_dir)
    rules = load_rules(source, args.private_rules, args.candidate_aliases)
    aliases = expanded_aliases(source, rules)
    rules = Rules(rules.entries, aliases)
    private_dir.mkdir(parents=True)
    save_json(private_dir / "aliases.private.json", {"full_to_alias": aliases})
    save_json(private_dir / "rules.private.json", {"version": 1, "replacements": [
        {"category": category, "private": private, "public": public}
        for category, private, public in rules.entries
    ]})
    source_refs = git(source, "for-each-ref", "--format=%(refname) %(objectname)")
    (private_dir / "source-refs.private.txt").write_bytes(source_refs)
    tips = resolve_refs(source, BRANCHES)
    save_json(private_dir / "input-tips.private.json", dict(zip(BRANCHES, tips)))
    check = tip_check(source, rules)
    save_json(private_dir / "tip-check.private.json", check)
    if check["status"] != "clean":
        return {"status": "blocked", "category": "feature_tip_not_clean", "scan": check}
    before_tree = git(source, "rev-parse", BRANCHES[1] + "^{tree}").strip()
    before_manifest = manifest(source, BRANCHES[1])
    save_json(private_dir / "input-feature-manifest.private.json", before_manifest)
    # Git copies objects rather than linking source objects; output has no remote.
    git(source, "clone", "--bare", "--no-hardlinks", str(source), str(output))
    git(output, "remote", "remove", "origin")
    for ref in git(output, "for-each-ref", "--format=%(refname)").decode("utf-8").splitlines():
        if ref not in BRANCHES:
            git(output, "update-ref", "-d", ref)
    for name in ("rewrite_public_history.py", "check_public_release.py"):
        shutil.copyfile(Path(__file__).parent / name, private_dir / name)
    save_json(private_dir / "callback.private.json", {"output": str(output), "private_dir": str(private_dir)})
    callback = " ".join(shlex.quote(part.replace("\\", "/")) for part in (
        sys.executable, "-B", "-I", "-X", "utf8", str(private_dir / "rewrite_public_history.py"),
        "_filter", "--state", str(private_dir / "callback.private.json"),
    ))
    env_filter = (
        f"GIT_AUTHOR_NAME='{PUBLIC_NAME}'; GIT_COMMITTER_NAME='{PUBLIC_NAME}'; "
        f"GIT_AUTHOR_EMAIL='{PUBLIC_EMAIL}'; GIT_COMMITTER_EMAIL='{PUBLIC_EMAIL}'; "
        'GIT_AUTHOR_DATE="${GIT_AUTHOR_DATE% *} +0000"; '
        'GIT_COMMITTER_DATE="${GIT_COMMITTER_DATE% *} +0000"; '
        "export GIT_AUTHOR_NAME GIT_COMMITTER_NAME GIT_AUTHOR_EMAIL GIT_COMMITTER_EMAIL "
        "GIT_AUTHOR_DATE GIT_COMMITTER_DATE"
    )
    env = dict(os.environ, FILTER_BRANCH_SQUELCH_WARNING="1", PYTHONDONTWRITEBYTECODE="1")
    command = ["git", "-C", str(output), "filter-branch", "--index-filter", callback + " --kind index",
               "--env-filter", env_filter, "--msg-filter", callback + " --kind message", "--", *BRANCHES]
    save_json(private_dir / "filter-command.private.json", command)
    process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, check=False)
    (private_dir / "filter-stdout.private.log").write_bytes(process.stdout)
    (private_dir / "filter-stderr.private.log").write_bytes(process.stderr)
    if process.returncode:
        raise ReleaseError("filter_failed_private_logs_available")
    mapping = verify_rewrite(source, output, rules, before_tree, before_manifest)
    save_json(private_dir / "commit-map.private.json", mapping)
    save_json(private_dir / "output-feature-manifest.private.json", manifest(output, BRANCHES[1]))
    # Backup refs remain only in the independent private rehearsal, never a plan.
    report = scan_history(output, BRANCHES, rules)
    save_json(private_dir / "history-scan.private.json", report)
    if git(source, "for-each-ref", "--format=%(refname) %(objectname)") != source_refs:
        raise ReleaseError("source_refs_changed")
    result = {
        "status": "verified" if report["status"] == "clean" else "blocked",
        "source_refs_unchanged": True, "feature_tree_and_modes_identical": True,
        "topology_times_and_modes_verified": True,
        "commits": len(mapping), "history_scan": report,
        "limits": "Local rehearsal only. No remote verification or publication; private backup refs retain original objects. Review/Gate2 and source-branch migration remain operator duties.",
    }
    save_json(private_dir / "result.private.json", result)
    return result


def commit_records(repo: Path) -> dict:
    oids = git(repo, "rev-list", "--reverse", "--topo-order", *BRANCHES, "--").decode("ascii").splitlines()
    records = {}
    for oid, _, data in objects(repo, oids):
        header, message = data.split(b"\n\n", 1)
        record = {"parents": [], "message": message}
        for line in header.splitlines():
            key, _, value = line.partition(b" ")
            if key == b"parent":
                record["parents"].append(value.decode("ascii"))
            elif key in (b"author", b"committer"):
                record[key.decode("ascii")] = value
        records[oid] = record
    return records


def verify_rewrite(source: Path, output: Path, rules: Rules, before_tree: bytes, before_manifest: list) -> dict:
    if git(output, "rev-parse", BRANCHES[1] + "^{tree}").strip() != before_tree or manifest(output, BRANCHES[1]) != before_manifest:
        raise ReleaseError("feature_tip_tree_changed")
    old, new = commit_records(source), commit_records(output)
    if len(old) != len(new):
        raise ReleaseError("topology_changed")
    # Traverse paired branch parents, rather than relying on timestamp ordering.
    pending = list(zip(resolve_refs(source, BRANCHES), resolve_refs(output, BRANCHES)))
    mapping = {}
    while pending:
        previous, current = pending.pop()
        if previous in mapping:
            if mapping[previous] != current:
                raise ReleaseError("shared_ancestor_changed")
            continue
        mapping[previous] = current
        a, b = old[previous], new[current]
        if len(a["parents"]) != len(b["parents"]):
            raise ReleaseError("parents_changed")
        pending.extend(zip(a["parents"], b["parents"]))
        if rules.transform(a["message"]) != b["message"]:
            raise ReleaseError("message_changed_unexpectedly")
        for role in ("author", "committer"):
            timestamp = a[role].rsplit(b" ", 2)[1]
            expected = f"{PUBLIC_NAME} <{PUBLIC_EMAIL}> ".encode("ascii") + timestamp + b" +0000"
            if b[role] != expected:
                raise ReleaseError("identity_or_timestamp_changed")
        old_modes = {path: mode for mode, _, _, path in tree_entries(source, previous) if not old_archive(path)}
        new_modes = {path: mode for mode, _, _, path in tree_entries(output, current)}
        if old_modes != new_modes:
            raise ReleaseError("historical_paths_or_modes_changed")
    if len(mapping) != len(old) or len(set(mapping.values())) != len(new):
        raise ReleaseError("topology_changed")
    for previous, current in zip(resolve_refs(source, BRANCHES), resolve_refs(output, BRANCHES)):
        if is_ancestor(output, previous, current):
            raise ReleaseError("old_tip_still_ancestor")
    return mapping


def filter_callback(args):
    state = read_json(args.state)
    output, private_dir = Path(state["output"]), Path(state["private_dir"])
    rules = load_rules(output, private_dir / "rules.private.json", private_dir / "aliases.private.json")
    if args.kind == "message":
        sys.stdout.buffer.write(rules.transform(sys.stdin.buffer.read()))
        return
    cache_file = private_dir / "blob-cache.private.json"
    cache = read_json(cache_file) if cache_file.exists() else {}
    entries = []
    updates = bytearray()
    for record in git(output, "ls-files", "--stage", "-z").split(b"\0"):
        if not record:
            continue
        meta, path = record.split(b"\t", 1)
        mode, oid, stage = meta.decode("ascii").split()
        if stage != "0" or mode not in ("100644", "100755"):
            raise ReleaseError("unsupported_index_entry")
        if old_archive(path):
            updates.extend(b"0 " + b"0" * 40 + b"\t" + path + b"\0")
        else:
            entries.append((mode, oid, path))
    missing = dict.fromkeys(oid for _, oid, _ in entries if oid not in cache)
    for oid, _, data in objects(output, missing):
        replacement = rules.transform(data)
        cache[oid] = (git(output, "hash-object", "-w", "--stdin", data=replacement).decode("ascii").strip()
                      if replacement != data else oid)
    for mode, oid, path in entries:
        if cache[oid] != oid:
            updates.extend(f"{mode} {cache[oid]}\t".encode("ascii") + path + b"\0")
    if updates:
        git(output, "update-index", "-z", "--index-info", data=bytes(updates))
    save_json(cache_file, cache)


def publication_command(repo: Path, leases: dict, remote: str) -> list[str]:
    if (not isinstance(leases, dict) or set(leases) != set(BRANCHES)
            or any(not isinstance(oid, str) or not re.fullmatch(r"[0-9a-f]{40}", oid) for oid in leases.values())
            or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", remote)):
        raise ReleaseError("invalid_exact_publication_plan")
    new = resolve_refs(repo, REWRITTEN)
    for branch, oid in zip(BRANCHES, new):
        if is_ancestor(repo, leases[branch], oid):
            raise ReleaseError("old_tip_still_ancestor")
    return ["git", "push", "--atomic", *(
        f"--force-with-lease={branch}:{leases[branch]}" for branch in BRANCHES
    ), remote, *(f"{source}:{target}" for source, target in zip(REWRITTEN, BRANCHES))]


def plan(args) -> dict:
    repo = repository_root(args.repo.resolve())
    leases = read_json(external_file(args.leases, repo))
    plan_file = args.plan_file.resolve()
    if plan_file.exists() or plan_file.is_relative_to(repo):
        raise ReleaseError("new_external_plan_file_required")
    command = publication_command(repo, leases, args.remote)
    plan_file.parent.mkdir(parents=True, exist_ok=True)
    save_json(plan_file, {"argv": command, "new_oids": dict(zip(REWRITTEN, resolve_refs(repo, REWRITTEN))),
                          "notice": "PRIVATE. Never refresh leases after rejection. Execute only after independent review and human approval."})
    return {"status": "plan_only", "command_template":
            "git push --atomic " + " ".join(f"--force-with-lease={ref}:<recorded-lease-{i}>" for i, ref in enumerate(BRANCHES, 1))
            + " <selected-remote> " + " ".join(f"{source}:{target}" for source, target in zip(REWRITTEN, BRANCHES)),
            "limits": "No push executed. Recheck exact leases without replacing them; rejection must stop publication. Only selected two refs, never backup refs."}


def main(argv=None) -> int:
    parser = QuietParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    rewrite_parser = commands.add_parser("rewrite", help="Independent local-only bare rewrite; no source writes")
    rewrite_parser.add_argument("--source", type=Path, required=True)
    rewrite_parser.add_argument("--output", type=Path, required=True)
    rewrite_parser.add_argument("--private-dir", type=Path, required=True)
    rewrite_parser.add_argument("--private-rules", type=Path, required=True)
    rewrite_parser.add_argument("--candidate-aliases", type=Path, required=True)
    plan_parser = commands.add_parser("plan", help="Write an external private plan, print only a redacted command; NEVER push")
    plan_parser.add_argument("--repo", type=Path, required=True)
    plan_parser.add_argument("--leases", type=Path, required=True)
    plan_parser.add_argument("--remote", required=True, help="Explicit remote name, no default")
    plan_parser.add_argument("--plan-file", type=Path, required=True)
    callback = commands.add_parser("_filter", help="Internal callback, for the independent output only")
    callback.add_argument("--state", type=Path, required=True)
    callback.add_argument("--kind", choices=("index", "message"), required=True)
    try:
        args = parser.parse_args(argv)
        if args.command == "_filter":
            filter_callback(args)
            return 0
        result = rewrite(args) if args.command == "rewrite" else plan(args)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return int(result["status"] == "blocked")
    except (ReleaseError, OSError, UnicodeError, ValueError) as error:
        # Never expose Git stderr, private JSON or filesystem paths on errors.
        category = str(error) if isinstance(error, ReleaseError) else "operation_failed"
        print(json.dumps({"status": "error", "category": category}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
