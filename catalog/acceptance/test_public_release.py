"""Offline acceptance of the real release tools, using only disposable Git repos.

No DB, network, Docker, production refs or actual private values are used. Private
rules deliberately classify reserved example identities that are otherwise safe.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCAN = ROOT / "tools" / "check_public_release.py"
REWRITE = ROOT / "tools" / "rewrite_public_history.py"
BRANCHES = ("refs/heads/main", "refs/heads/feat/catalog-foundation")
FAKE_PERSON = "Synthetic Operator"
FAKE_EMAIL = "operator@example.invalid"
FAKE_ENDPOINT = "private-service.example.invalid"
PUBLIC_ENDPOINT = "service.example.invalid"
OLD_ARCHIVE = "handoff/" + "original.txt"


def run(argv, cwd=None, env=None):
    settings = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                    GIT_TERMINAL_PROMPT="0", PYTHONDONTWRITEBYTECODE="1")
    if env:
        settings.update(env)
    return subprocess.run([str(arg) for arg in argv], cwd=cwd, env=settings,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def git(repo, *args, env=None):
    result = run(["git", "-c", "core.autocrlf=false", "-C", repo, *args], env=env)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    return result.stdout


def tool(script, *args):
    return run([sys.executable, "-B", "-I", "-X", "utf8", script, *args])


def put(repo, name, text):
    target = repo / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="\n")


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def commit(repo, message, seconds):
    env = {"GIT_AUTHOR_NAME": FAKE_PERSON, "GIT_COMMITTER_NAME": "Synthetic Reviewer",
           "GIT_AUTHOR_EMAIL": FAKE_EMAIL, "GIT_COMMITTER_EMAIL": "reviewer@example.invalid",
           "GIT_AUTHOR_DATE": f"@{seconds} +0530", "GIT_COMMITTER_DATE": f"@{seconds + 1} -0400"}
    git(repo, "add", "--all")
    git(repo, "commit", "-m", message, env=env)
    return git(repo, "rev-parse", "HEAD").decode().strip()


def snapshot(repo):
    return {p.relative_to(repo).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in repo.rglob("*") if p.is_file()}


def entries(repo, ref):
    output = {}
    for record in git(repo, "ls-tree", "-rz", ref).split(b"\0"):
        if record:
            meta, path = record.split(b"\t", 1)
            mode, _, oid = meta.split()
            output[path.decode("utf-8")] = (mode.decode(), oid.decode())
    return output


@pytest.fixture
def source(tmp_path):
    repo = tmp_path / "source"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    put(repo, ".gitignore", ".env\n.venv/\ndata/\n")
    put(repo, "旧版本.py", f'VERSION = 1\nENDPOINT = "{FAKE_ENDPOINT}"\n')
    put(repo, "重复.txt", FAKE_ENDPOINT + "\n")
    put(repo, "duplicate.txt", FAKE_ENDPOINT + "\n")
    put(repo, "可执行.sh", "#!/bin/sh\nprintf 'example\\n'\n")
    put(repo, "handoff/README.md", "Public redacted summary; detailed originals are private.\n")
    put(repo, OLD_ARCHIVE, FAKE_EMAIL + "\n")
    root = commit(repo, f"root by {FAKE_PERSON} <{FAKE_EMAIL}>", 1700000000)
    git(repo, "update-index", "--chmod=+x", "可执行.sh")
    # Commit the index-only executable bit without re-adding files on Windows.
    env = {"GIT_AUTHOR_NAME": FAKE_PERSON, "GIT_COMMITTER_NAME": FAKE_PERSON,
           "GIT_AUTHOR_EMAIL": FAKE_EMAIL, "GIT_COMMITTER_EMAIL": FAKE_EMAIL,
           "GIT_AUTHOR_DATE": "@1700000100 +0530", "GIT_COMMITTER_DATE": "@1700000101 -0400"}
    git(repo, "commit", "-m", f"main derives from {root[:9]}", env=env)
    main = git(repo, "rev-parse", "HEAD").decode().strip()
    git(repo, "checkout", "-b", "feat/catalog-foundation")
    put(repo, "旧版本.py", f'VERSION = 2\nENDPOINT = "{PUBLIC_ENDPOINT}"\n')
    put(repo, "重复.txt", PUBLIC_ENDPOINT + "\n")
    put(repo, "duplicate.txt", PUBLIC_ENDPOINT + "\n")
    (repo / OLD_ARCHIVE).unlink()
    feature = commit(repo, f"feature follows {main[:7]}", 1700000200)
    # Unrelated local branch must not escape the restricted output or plan.
    git(repo, "branch", "private-backup", root)
    rules = tmp_path / "rules.private.json"
    write_json(rules, {"version": 1, "replacements": [
        {"category": "identity", "private": FAKE_PERSON, "public": "Project Contributors"},
        {"category": "identity", "private": FAKE_EMAIL, "public": "contributors@example.invalid"},
        {"category": "endpoint", "private": FAKE_ENDPOINT, "public": PUBLIC_ENDPOINT},
    ]})
    aliases = tmp_path / "aliases.private.json"
    write_json(aliases, {"full_to_alias": {root: "Candidate-root", main: "Candidate-main"}})
    return {"repo": repo, "rules": rules, "aliases": aliases, "root": root,
            "main": main, "feature": feature, "base": tmp_path}


def rewrite(source, suffix=""):
    output = source["base"] / ("rewritten" + suffix + ".git")
    private = source["base"] / ("result" + suffix)
    result = tool(REWRITE, "rewrite", "--source", source["repo"], "--output", output,
                  "--private-dir", private, "--private-rules", source["rules"],
                  "--candidate-aliases", source["aliases"])
    return result, output, private


@pytest.fixture
def rewritten(source):
    before = snapshot(source["repo"])
    result, output, private = rewrite(source)
    # Synthetic logs may be shown on test failure; real inputs are never used here.
    logs = (private / "filter-stderr.private.log")
    assert result.returncode == 0, (result.stdout, result.stderr, logs.read_bytes() if logs.exists() else b"")
    assert snapshot(source["repo"]) == before
    return source, output, private, result


def test_history_scan_finds_early_blobs_messages_and_both_identities(source):
    current = tool(SCAN, "--repo", source["repo"], "--private-rules", source["rules"])
    assert current.returncode == 0, current.stdout
    historical = tool(SCAN, "--repo", source["repo"], "--private-rules", source["rules"],
                      "--candidate-aliases", source["aliases"], "--refs", *BRANCHES)
    assert historical.returncode == 1
    report = json.loads(historical.stdout)
    categories = {row["category"] for row in report["findings"]}
    assert {"identity", "endpoint", "candidate", "nonpublic_identity", "old_archive"} <= categories
    locations = [row["location"] for row in report["findings"]]
    assert any(location.endswith(":author") for location in locations)
    assert any(location.endswith(":committer") for location in locations)
    assert any(location.endswith(":message") for location in locations)
    for forbidden in (FAKE_PERSON, FAKE_EMAIL, FAKE_ENDPOINT, source["root"], str(source["rules"])):
        assert forbidden.encode() not in historical.stdout + historical.stderr
    assert report["counts"]["commit"] == 3


def test_worktree_scans_index_untracked_unicode_hidden_and_non_markdown(source):
    repo = source["repo"]
    put(repo, "待提交.jsonl", json.dumps({"endpoint": FAKE_ENDPOINT}))
    put(repo, ".hidden", FAKE_EMAIL)
    put(repo, "staged.txt", FAKE_EMAIL)
    git(repo, "add", "staged.txt")
    put(repo, "staged.txt", "worktree clean, staged value is not\n")
    put(repo, ".env", FAKE_EMAIL)
    put(repo, ".venv/private.txt", FAKE_EMAIL)
    put(repo, "data/private.txt", FAKE_EMAIL)
    result = tool(SCAN, "--repo", repo, "--private-rules", source["rules"])
    assert result.returncode == 1
    report = json.loads(result.stdout)
    locations = {row["location"] for row in report["findings"]}
    assert {"worktree:待提交.jsonl", "worktree:.hidden", "index:staged.txt"} <= locations
    assert not any(".env" in row["location"] or ".venv/" in row["location"] or "data/private" in row["location"] for row in report["coverage"])


def test_private_filename_is_aliased_and_original_archive_readme_is_exempt(source):
    repo = source["repo"]
    put(repo, FAKE_EMAIL + ".txt", "safe contents\n")
    put(repo, OLD_ARCHIVE, "safe contents\n")
    result = tool(SCAN, "--repo", repo, "--private-rules", source["rules"])
    assert result.returncode == 1
    assert FAKE_EMAIL.encode() not in result.stdout
    report = json.loads(result.stdout)
    assert any(row["category"] == "old_archive" for row in report["findings"])
    assert not any("handoff/README.md" in row["location"] for row in report["findings"])


def test_generic_products_academic_references_reserved_examples_and_formats(source):
    repo = source["repo"]
    put(repo, "examples.txt", "Tailscale NAS Docker BnF IDP\nhttps://example.invalid\n192.0.2.10\n/data /backup /cache /srv/example/data\n")
    (repo / "binary.dat").write_bytes(b"\x00\x01\xff")
    result = tool(SCAN, "--repo", repo)
    assert result.returncode == 0, result.stdout
    assert json.loads(result.stdout)["counts"]["binary-excluded"] == 1
    (repo / "unknown.dat").write_bytes(b"\xff\xfeX")
    result = tool(SCAN, "--repo", repo)
    assert result.returncode == 1
    assert "unrecognized-format" in result.stdout.decode()


def test_generic_shapes_and_old_archive_index_reference(source):
    repo = source["repo"]
    put(repo, "shape.txt", "192." + "168.3.4\n" + "C:/" + "Users/ExampleOperator\n" + OLD_ARCHIVE)
    result = tool(SCAN, "--repo", repo)
    assert result.returncode == 1
    categories = {row["category"] for row in json.loads(result.stdout)["findings"]}
    assert {"private_network_shape", "personal_home_shape", "archive_reference"} <= categories
    assert b"ExampleOperator" not in result.stdout


@pytest.mark.parametrize("bad", [
    "not-json", '{"version": 1, "replacements": [{"category": "arbitrary-private-category"}]}',
    '{"version": 1, "replacements": [{"category": {"private": "value"}}]}',
])
def test_invalid_private_input_does_not_echo_values_or_paths(source, bad):
    rules = source["base"] / "private-input-name.json"
    rules.write_text(bad, encoding="utf-8")
    result = tool(SCAN, "--repo", source["repo"], "--private-rules", rules)
    assert result.returncode == 2
    assert b"Traceback" not in result.stderr
    for value in (bad, str(rules), "private-input-name", "arbitrary-private-category"):
        assert value.encode() not in result.stdout + result.stderr


def test_private_rules_inside_repo_rejected(source):
    rules = source["repo"] / "rules.json"
    rules.write_bytes(source["rules"].read_bytes())
    result = tool(SCAN, "--repo", source["repo"], "--private-rules", rules)
    assert result.returncode == 2
    assert "private_input_must_be_external" in result.stdout.decode()


def test_rewrite_preserves_tip_source_modes_unicode_root_topology_and_cache(rewritten):
    source, output, private, result = rewritten
    assert json.loads(result.stdout)["status"] == "verified"
    assert git(output, "rev-parse", BRANCHES[1] + "^{tree}") == git(source["repo"], "rev-parse", BRANCHES[1] + "^{tree}")
    assert entries(output, BRANCHES[1]) == entries(source["repo"], BRANCHES[1])
    assert entries(output, BRANCHES[1])["可执行.sh"][0] == "100755"
    assert entries(output, BRANCHES[1])["旧版本.py"][0] == "100644"
    mapping = json.loads((private / "commit-map.private.json").read_text())
    assert len(mapping) == 3
    assert git(output, "rev-list", "--parents", "-n", "1", mapping[source["root"]]).decode().split() == [mapping[source["root"]]]
    assert git(output, "rev-parse", BRANCHES[1] + "^").decode().strip() == mapping[source["main"]]
    assert git(output, "merge-base", *BRANCHES).decode().strip() == mapping[source["main"]]
    assert git(output, "remote") == b""
    assert git(output, "for-each-ref", "--format=%(refname)", "refs/heads").decode().splitlines() == sorted(BRANCHES)
    root_entries = entries(output, mapping[source["root"]])
    assert OLD_ARCHIVE not in root_entries
    assert "handoff/README.md" in root_entries
    assert root_entries["重复.txt"][1] == root_entries["duplicate.txt"][1]
    assert OLD_ARCHIVE in entries(source["repo"], source["root"])
    cache = json.loads((private / "blob-cache.private.json").read_text())
    assert entries(source["repo"], source["root"])["duplicate.txt"][1] in cache
    old_python = git(output, "show", mapping[source["root"]] + ":旧版本.py").decode("utf-8")
    ast.parse(old_python)
    assert "VERSION = 1" in old_python and PUBLIC_ENDPOINT in old_python
    assert "VERSION = 2" in git(output, "show", BRANCHES[1] + ":旧版本.py").decode()
    # Copied original loose objects must not share hard links with the source.
    for path in (source["repo"] / ".git" / "objects").glob("??/*"):
        copied = output / "objects" / path.parent.name / path.name
        if copied.exists():
            assert not os.path.samefile(path, copied)
    aliases = json.loads((private / "aliases.private.json").read_text())["full_to_alias"]
    assert aliases[source["root"]] == "Candidate-root"
    assert aliases[source["feature"]].startswith("Candidate-extension-")
    assert source["feature"] not in json.loads(source["aliases"].read_text())["full_to_alias"]


def test_rewrite_full_history_identity_time_messages_and_scan(rewritten):
    source, output, private, result = rewritten
    mapping = json.loads((private / "commit-map.private.json").read_text())
    for old, new in mapping.items():
        old_data = git(source["repo"], "cat-file", "commit", old)
        new_data = git(output, "cat-file", "commit", new)
        for role in (b"author ", b"committer "):
            before = next(line for line in old_data.splitlines() if line.startswith(role))
            after = next(line for line in new_data.splitlines() if line.startswith(role))
            assert before.rsplit(b" ", 2)[1] == after.rsplit(b" ", 2)[1]
            assert b"Project Contributors <contributors@example.invalid>" in after
            assert after.endswith(b"+0000")
    message = git(output, "show", "-s", "--format=%B", BRANCHES[0])
    assert b"Candidate-root" in message
    assert source["root"][:9].encode() not in message
    scan = tool(SCAN, "--repo", output, "--private-rules", source["rules"],
                "--candidate-aliases", private / "aliases.private.json", "--refs", *BRANCHES)
    assert scan.returncode == 0, scan.stdout
    for value in (FAKE_EMAIL, FAKE_PERSON, FAKE_ENDPOINT, str(source["rules"]), *mapping):
        assert value.encode() not in result.stdout + result.stderr


def test_rewrite_blocks_dirty_or_still_private_feature_tip_without_touching_source(source):
    put(source["repo"], "pending.txt", "not committed\n")
    before = snapshot(source["repo"])
    result, output, _ = rewrite(source, "dirty")
    assert result.returncode == 2
    assert not output.exists()
    assert snapshot(source["repo"]) == before
    commit(source["repo"], "pending committed", 1700000300)
    put(source["repo"], "leak.txt", FAKE_ENDPOINT)
    commit(source["repo"], "unclean feature tip", 1700000400)
    before = snapshot(source["repo"])
    result, output, private = rewrite(source, "leak")
    assert result.returncode == 1
    assert json.loads(result.stdout)["category"] == "feature_tip_not_clean"
    assert not output.exists()
    assert snapshot(source["repo"]) == before
    assert (private / "tip-check.private.json").exists()
    assert FAKE_ENDPOINT.encode() not in result.stdout


def test_alias_transform_preserves_checksums_and_literal_rules_are_nonrecursive(source):
    spec = importlib.util.spec_from_file_location("release_scan_under_test", SCAN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    oid = source["root"]
    rules = module.Rules([("identity", "alpha", "beta"), ("identity", "beta", "gamma")], {oid: "Candidate-root"})
    checksum = oid + "a" * 24
    text = f"alpha beta {oid[:7]} {oid} HEAD{oid[:7]} {checksum}\n".encode()
    assert rules.transform(text) == f"beta gamma Candidate-root Candidate-root HEADCandidate-root {checksum}\n".encode()
    utf16 = ("alpha\n").encode("utf-16")
    assert rules.transform(utf16).decode("utf-16") == "beta\n"


def test_exact_leases_and_atomic_push_really_reject_concurrent_ref(rewritten):
    source, output, private, _ = rewritten
    remote = source["base"] / "synthetic-remote.git"
    git(source["repo"], "init", "--bare", remote)
    git(source["repo"], "push", str(remote), *(f"{ref}:{ref}" for ref in BRANCHES))
    for ref in BRANCHES:
        new = git(output, "rev-parse", ref).decode().strip()
        git(output, "update-ref", ref.replace("refs/heads/", "refs/rewritten/"), new)
    git(output, "remote", "add", "synthetic", str(remote))
    leases = {ref: git(remote, "rev-parse", ref).decode().strip() for ref in BRANCHES}
    lease_file = private / "leases.private.json"
    write_json(lease_file, leases)
    plan_file = private / "push-plan.private.json"
    before = git(remote, "show-ref")
    plan = tool(REWRITE, "plan", "--repo", output, "--leases", lease_file,
                "--remote", "synthetic", "--plan-file", plan_file)
    assert plan.returncode == 0, plan.stdout
    assert git(remote, "show-ref") == before  # plan never pushes
    argv = json.loads(plan_file.read_text())["argv"]
    assert argv[:3] == ["git", "push", "--atomic"]
    assert argv[3:5] == [f"--force-with-lease={ref}:{leases[ref]}" for ref in BRANCHES]
    assert argv[-2:] == [f"{ref.replace('refs/heads/', 'refs/rewritten/')}:{ref}" for ref in BRANCHES]
    assert not {"--force", "--mirror", "--all"}.intersection(argv)
    assert all(oid.encode() not in plan.stdout for oid in leases.values())
    # The remote main advances independently after lease capture, feature does not.
    git(remote, "update-ref", BRANCHES[0], source["feature"], source["main"])
    concurrent = git(remote, "show-ref")
    rejected = run(argv, cwd=output)
    assert rejected.returncode != 0
    assert b"stale info" in rejected.stderr
    assert git(remote, "show-ref") == concurrent
    assert git(remote, "rev-parse", BRANCHES[1]).decode().strip() == leases[BRANCHES[1]]
    assert json.loads(lease_file.read_text()) == leases
    # A SEPARATE untouched synthetic bare proves this exact plan can also succeed.
    fresh = source["base"] / "synthetic-fresh.git"
    git(source["repo"], "init", "--bare", fresh)
    git(source["repo"], "push", str(fresh), *(f"{ref}:{ref}" for ref in BRANCHES))
    git(output, "remote", "set-url", "synthetic", str(fresh))
    accepted = run(argv, cwd=output)
    assert accepted.returncode == 0, accepted.stderr
    for ref in BRANCHES:
        assert git(fresh, "rev-parse", ref) == git(output, "rev-parse", ref)
    assert len(git(fresh, "for-each-ref", "--format=%(refname)").splitlines()) == 2


def test_rewrite_refuses_in_place_existing_and_nested_destinations(source):
    before = snapshot(source["repo"])
    for number, output in enumerate((source["repo"], source["repo"] / "nested-output")):
        result = tool(REWRITE, "rewrite", "--source", source["repo"], "--output", output,
                      "--private-dir", source["base"] / f"refused-result-{number}",
                      "--private-rules", source["rules"], "--candidate-aliases", source["aliases"])
        assert result.returncode == 2
        assert snapshot(source["repo"]) == before
        assert not (source["base"] / f"refused-result-{number}").exists()


def test_subdirectory_scan_still_covers_entire_repository(source):
    put(source["repo"], "outside-subdir.txt", FAKE_EMAIL)
    result = tool(SCAN, "--repo", source["repo"] / "handoff", "--private-rules", source["rules"])
    assert result.returncode == 1
    assert any(row["location"] == "worktree:outside-subdir.txt" for row in json.loads(result.stdout)["findings"])


def test_publication_plan_rejects_missing_extra_or_inexact_leases(rewritten):
    source, output, private, _ = rewritten
    for ref in BRANCHES:
        git(output, "update-ref", ref.replace("refs/heads/", "refs/rewritten/"), git(output, "rev-parse", ref).decode().strip())
    for number, leases in enumerate((
        {BRANCHES[0]: source["main"]},
        {BRANCHES[0]: source["main"][:7], BRANCHES[1]: source["feature"]},
        {BRANCHES[0]: source["main"], BRANCHES[1]: source["feature"], "refs/heads/other": source["root"]},
    )):
        lease_file = private / f"bad-leases-{number}.json"
        write_json(lease_file, leases)
        plan_file = private / f"must-not-exist-{number}.json"
        result = tool(REWRITE, "plan", "--repo", output, "--leases", lease_file,
                      "--remote", "synthetic", "--plan-file", plan_file)
        assert result.returncode == 2
        assert not plan_file.exists()
        assert b"invalid_exact_publication_plan" in result.stdout
    # An unrewritten main cannot be published even with an otherwise exact plan.
    git(output, "update-ref", "refs/rewritten/main", source["main"])
    lease_file = private / "valid-leases.json"
    write_json(lease_file, {BRANCHES[0]: source["main"], BRANCHES[1]: source["feature"]})
    result = tool(REWRITE, "plan", "--repo", output, "--leases", lease_file,
                  "--remote", "synthetic", "--plan-file", private / "unsafe-plan.json")
    assert result.returncode == 2
    assert b"old_tip_still_ancestor" in result.stdout


@pytest.mark.parametrize("script", [SCAN, REWRITE])
def test_cli_help_and_public_source_encoding(script):
    result = tool(script, "--help")
    assert result.returncode == 0
    data = script.read_bytes()
    assert b"\r" not in data and not data.startswith(b"\xef\xbb\xbf")
    ast.parse(data.decode("utf-8"), feature_version=(3, 12))
