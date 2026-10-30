"""PRIV-02: real local subprocess/files; no Docker, daemon loop or host data access.

Compose/shell wiring checks are source contracts, not a deployment proof.
The only executed paths are missing configuration and a synthetic stitch queue.
"""

import ast
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOST_KEYS = ("DH_DEPLOY_DIR", "DH_HOST_DATA_DIR", "DH_HOST_CACHE_DIR")
SCRIPTS = ("auto_huge.sh", "auto_huge_boot.sh", "auto_huge_daemon.sh")
# Fixed public vector shared by the real ID functions and stitch cache cleanup.
REL = "示例/卷 A/合并长卷.tif"
FID = "56S65L6LL-WNtyBBL-WQiOW5tumVv-WNty50aWY"
CACHE_KEY = "6eae65b35653ce17"


def clean_env(tmp_path):
    # Do not inherit deployment settings, Python startup hooks or shell rc hooks.
    env = {key: value for key, value in os.environ.items()
           if key.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP"}}
    env.update(HOME=str(tmp_path), PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
    return env


def snapshot(directory):
    return {path.relative_to(directory).as_posix():
            None if path.is_dir() else path.read_bytes()
            for path in directory.rglob("*")}


@pytest.fixture
def queue(tmp_path):
    # Space, non-ASCII and shell metacharacters are literal filesystem names.
    data = tmp_path / "data 示例 $literal;"
    cache = tmp_path / "cache 示例 $literal;"
    out = cache / "stitch_out"
    data.mkdir()
    out.mkdir(parents=True)
    source = out / "job.tif"
    source.write_bytes(b"II\x2a\x00\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00synthetic stitch output")
    side = out / "job.json"
    side.write_text(json.dumps({"target": REL}, ensure_ascii=False), encoding="utf-8")
    return data, cache, source, side


@pytest.mark.parametrize("script,argument", [
    ("auto_huge.sh", ""), ("auto_huge_boot.sh", "start"),
    ("auto_huge_boot.sh", "stop"), ("auto_huge_daemon.sh", ""),
])
@pytest.mark.parametrize("missing,empty", [
    (None, False), *[(key, empty) for key in HOST_KEYS for empty in (False, True)],
])
def test_shell_missing_configuration_fails_before_any_action(
    tmp_path, queue, script, argument, missing, empty,
):
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash is required for the real shell subprocess check")
    text = (ROOT / script).read_text(encoding="utf-8")
    # Check the actual entry before executing: no preflight command may reach a
    # real ps/kill/Docker even if a later edit accidentally moves validation.
    prefix = [line for line in text.splitlines() if line and not line.startswith("#")][:3]
    assert prefix == [f': "${{{key}:?Set {key}}}"' for key in HOST_KEYS]
    data, cache, _, _ = queue
    deploy = tmp_path / "deployment 示例 $literal;"
    deploy.mkdir()
    # A boot copy may live outside the deployment directory. It must not infer it.
    copy = tmp_path / "startup copy.sh"
    copy.write_text(text, encoding="utf-8", newline="\n")
    env = clean_env(tmp_path)
    if missing is not None:
        env.update(dict(zip(HOST_KEYS, (deploy.as_posix(), data.as_posix(), cache.as_posix()))))
        if empty:
            env[missing] = ""
        else:
            del env[missing]
    before = snapshot(tmp_path)
    args = [bash, "--noprofile", "--norc", "-x", copy.as_posix()]
    if argument:
        args.append(argument)
    result = subprocess.run(args, env=env, cwd=tmp_path, capture_output=True,
                            encoding="utf-8", timeout=10, check=False)
    expected = missing or "DH_DEPLOY_DIR"
    assert result.returncode != 0
    assert f"Set {expected}" in result.stderr
    assert result.stdout == ""
    # xtrace contains only the successful ':' checks before the failing check.
    commands = [line for line in result.stderr.splitlines() if line.startswith("+")]
    assert all(line.startswith("+ : ") for line in commands), result.stderr
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("missing,empty", [
    (None, False), ("DATA_DIR", False), ("DATA_DIR", True),
    ("CACHE_DIR", False), ("CACHE_DIR", True),
])
def test_stitch_missing_configuration_fails_without_touching_queue(tmp_path, queue, missing, empty):
    data, cache, _, _ = queue
    env = clean_env(tmp_path)
    # HOST variables alone are not implicit fallbacks for this Python entry.
    env.update(DH_HOST_DATA_DIR=str(data), DH_HOST_CACHE_DIR=str(cache))
    if missing is not None:
        env.update(DATA_DIR=str(data), CACHE_DIR=str(cache))
        if empty:
            env[missing] = ""
        else:
            del env[missing]
    before = snapshot(tmp_path)
    result = subprocess.run(
        [sys.executable, "-B", "-I", "-X", "utf8", str(ROOT / "stitch_apply.py")],
        env=env, cwd=tmp_path, capture_output=True, encoding="utf-8", timeout=10, check=False,
    )
    assert result.returncode != 0
    assert f"{missing or 'DATA_DIR'} must be configured" in result.stderr
    assert result.stdout == ""
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("explicit_source", [False, True])
def test_stitch_real_queue_uses_configured_roots_and_preserves_mapping(tmp_path, queue, explicit_source):
    data, cache, source, side = queue
    if explicit_source:
        source = source.rename(source.with_name("source 示例 $literal;.tif"))
        side.write_text(json.dumps({"target": REL, "source_name": source.name}, ensure_ascii=False),
                        encoding="utf-8")
    payload = source.read_bytes()
    target = data / REL
    target.parent.mkdir(parents=True)
    target.write_bytes(b"old synthetic output")
    pyramid = cache / "pyramids" / CACHE_KEY
    pyramid.mkdir(parents=True)
    (pyramid / "old.dzi").write_text("old synthetic tiles", encoding="utf-8")
    thumbs = cache / "thumbs"
    thumbs.mkdir()
    (thumbs / f"{CACHE_KEY}.jpg").write_bytes(b"old legacy thumbnail")
    # Keep the known v3-thumbnail behavior; privacy work does not fix it.
    v3 = thumbs / f"v3_{CACHE_KEY}.jpg"
    v3.write_bytes(b"unchanged v3 thumbnail")
    unrelated = cache / "pyramids" / "unrelated"
    unrelated.mkdir()
    (unrelated / "keep.dzi").write_bytes(b"unrelated cached output")
    state = {"done": {"older.tif": {"bytes": 12}}, "failed": {}, "attempts": {},
             "deferred": {"waiting.tif": {"ts": 123}}, "current": "untouched"}
    state_path = cache / "pyramid_build_state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    # Defaults relative to cwd must not select this decoy queue.
    decoy = tmp_path / "cache" / "stitch_out"
    decoy.mkdir(parents=True)
    (decoy / "ignore.json").write_text('{"target": "ignore.tif"}', encoding="utf-8")
    (decoy / "ignore.tif").write_bytes(b"decoy")
    decoy_before = snapshot(decoy)
    env = clean_env(tmp_path)
    env.update(DATA_DIR=str(data), CACHE_DIR=str(cache))
    command = [sys.executable, "-B", "-I", "-X", "utf8", str(ROOT / "stitch_apply.py")]
    result = subprocess.run(command, env=env, cwd=tmp_path, capture_output=True,
                            encoding="utf-8", timeout=10, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert target.read_bytes() == payload
    assert not source.exists() and not side.exists()
    assert not Path(str(target) + ".stitchtmp").exists()
    assert not Path(str(state_path) + ".tmp").exists()
    assert not pyramid.exists()
    assert not (thumbs / f"{CACHE_KEY}.jpg").exists()
    assert v3.read_bytes() == b"unchanged v3 thumbnail"
    assert (unrelated / "keep.dzi").read_bytes() == b"unrelated cached output"
    updated = json.loads(state_path.read_text(encoding="utf-8"))
    entry = updated["deferred"].pop(REL)
    assert set(entry) == {"ts"} and isinstance(entry["ts"], int) and entry["ts"] > 0
    assert updated == state
    assert f"已应用: {REL}" in (cache / "stitch_apply.log").read_text(encoding="utf-8")
    assert snapshot(decoy) == decoy_before
    before = snapshot(tmp_path)
    again = subprocess.run(command, env=env, cwd=tmp_path, capture_output=True,
                           encoding="utf-8", timeout=10, check=False)
    assert again.returncode == 0 and again.stderr == ""
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("name", ["app.py", "pyramid_worker.py"])
def test_actual_id_functions_match_fixed_public_vector(name):
    # Compile only the real pure ID functions, avoiding module startup and libvips.
    tree = ast.parse((ROOT / name).read_text(encoding="utf-8"), feature_version=(3, 12))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in {"encode_id", "file_hash"}]
    assert len(functions) == 2
    namespace = {"base64": base64, "hashlib": hashlib}
    exec(compile(ast.Module(body=functions, type_ignores=[]), name, "exec"), namespace)
    assert namespace["encode_id"](REL) == FID
    assert namespace["file_hash"](FID) == CACHE_KEY


def test_compose_host_mounts_and_existing_safety_contracts():
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    sections = re.split(r"^  ([\w-]+):\n", text, flags=re.MULTILINE)
    services = dict(zip(sections[1::2], sections[2::2]))
    assert list(services) == ["pyramid-builder", "pyramid-huge", "dunhuang-viewer"]
    for name, memory, mode in (("pyramid-builder", "1536m", "ro"),
                               ("pyramid-huge", "2304m", "ro"),
                               ("dunhuang-viewer", "2048m", "rw")):
        section = services[name]
        assert f'"${{DH_HOST_DATA_DIR:?Set DH_HOST_DATA_DIR}}:/data:{mode}"' in section
        assert '"${DH_HOST_CACHE_DIR:?Set DH_HOST_CACHE_DIR}:/cache"' in section
        assert f"    mem_limit: {memory}\n" in section
        assert f"    memswap_limit: {memory}\n" in section
        assert "      - VIPS_CONCURRENCY=1\n" in section
        if name != "dunhuang-viewer":
            assert 'command: ["python", "-u", "pyramid_worker.py"]' in section
            assert "restart: on-failure" in section
            assert "- DATA_DIR=/data" in section and "- CACHE_DIR=/cache" in section
    viewer = services["dunhuang-viewer"]
    assert '"${DH_HOST_STATIC_DIR:-./static}:/app/static:ro"' in viewer
    assert "    env_file:\n      - .env\n" in viewer
    assert '      - "8503:8000"' in viewer
    assert "restart: unless-stopped" in viewer
    for value in ("CACHE_MAX_GB=600", "TILE_SIZE=512", "TILE_QUALITY=82", "MEM_GUARD_MB=900",
                  "FULL_DZI_MAX_PIXELS=350000000", "PREVIEW_LONG_EDGE=10000",
                  "PREVIEW_MAX_PIXELS=20000000", "THUMB_WORKERS=2",
                  "THUMB_VIPS_MAX_PIXELS=30000000", "PREVIEW_VIPS_MAX_PIXELS=30000000"):
        assert f"      - {value}\n" in viewer
    assert "- BUILD_MEM_FLOOR_MB=1200" in services["pyramid-builder"]
    assert "- HUGE_PIXELS=400000000" in services["pyramid-builder"]
    assert "- HUGE_WIDTH=100000" in services["pyramid-builder"]
    assert "- BUILD_MEM_FLOOR_MB=1000" in services["pyramid-huge"]
    assert "- PROCESS_DEFERRED=1" in services["pyramid-huge"]
    assert text.count("- BUILD_STRIP_MB=96") == 2


def test_shell_path_wiring_and_public_example():
    one = (ROOT / "auto_huge.sh").read_text(encoding="utf-8")
    boot = (ROOT / "auto_huge_boot.sh").read_text(encoding="utf-8")
    daemon = (ROOT / "auto_huge_daemon.sh").read_text(encoding="utf-8")
    assert 'nohup "$DH_DEPLOY_DIR/auto_huge_daemon.sh"' in boot
    for text in (one, daemon):
        assert 'python3 - "$DH_HOST_CACHE_DIR/pyramid_build_state.json"' in text
        assert "json.load(open(sys.argv[1]))" in text
        assert 'cd "$DH_DEPLOY_DIR" && /usr/local/bin/docker-compose up -d pyramid-huge' in text
    assert 'DATA_DIR="$DH_HOST_DATA_DIR" CACHE_DIR="$DH_HOST_CACHE_DIR" python3 "$DH_DEPLOY_DIR/stitch_apply.py" >> "$DH_HOST_CACHE_DIR/auto_huge.log"' in daemon
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    for key in (*HOST_KEYS, "AUTH_USER", "AUTH_PASS", "AUTH_SECRET"):
        assert re.search(rf"^{key}=$", example, re.MULTILINE)
    assert "DH_HOST_STATIC_DIR=./static\n" in example


@pytest.mark.parametrize("name", [
    "docker-compose.yml", ".env.example", *SCRIPTS, "stitch_apply.py",
    "app.py", "pyramid_worker.py", "catalog/acceptance/test_public_runtime.py",
])
def test_assigned_sources_utf8_lf_and_python312_syntax(name):
    raw = (ROOT / name).read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf") and b"\r" not in raw
    text = raw.decode("utf-8")
    if name.endswith(".py"):
        compile(ast.parse(text, filename=name, feature_version=(3, 12)), name, "exec")
