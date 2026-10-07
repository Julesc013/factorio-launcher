"""Guarded normal local commits; callers retain task/effect authorization.

The candidate object is verified before the branch moves. This does not
intercept raw Git, repair history, disable hooks, or sign commits.
"""

from __future__ import annotations

import hashlib
import os
import re
import queue
import subprocess
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator


MAX_MESSAGE_BYTES = 128 * 1024
MAX_INDEX_BYTES = 16 * 1024 * 1024
MAX_PATHS = 256
COMMIT_HOOKS = (
    "pre-commit", "prepare-commit-msg", "commit-msg", "post-commit",
    "reference-transaction",
)
REDIRECT_ENV = (
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_CONFIG", "GIT_CONFIG_SYSTEM", "GIT_CONFIG_PARAMETERS",
)


class CommitRefusal(ValueError):
    """An input or supported-operation condition was not satisfied."""


def _validated_git_environment() -> dict[str, str]:
    env = dict(os.environ)
    redirects = [name for name in REDIRECT_ENV if name in env]
    if redirects:
        raise CommitRefusal("Git redirection environment is outside this path: "
                            + ", ".join(redirects))
    selected = {name: env[name] for name in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM") if name in env}
    null_global = selected.get("GIT_CONFIG_GLOBAL", "")
    same_null = (null_global.casefold() == os.devnull.casefold() if os.name == "nt"
                 else null_global == os.devnull)
    if selected and (set(selected) != {"GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM"}
                     or not same_null or selected["GIT_CONFIG_NOSYSTEM"] != "1"):
        raise CommitRefusal("Git config isolation must match the existing runner null-global/no-system pair")
    runtime_names = {name for name in env if name.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))}
    raw_count = env.get("GIT_CONFIG_COUNT")
    if raw_count is None:
        if runtime_names:
            raise CommitRefusal("runtime Git configuration pairs lack a count")
        return env
    if not re.fullmatch(r"[0-9]{1,2}", raw_count) or int(raw_count) > 16:
        raise CommitRefusal("runtime Git configuration requires a finite count up to16")
    count = int(raw_count)
    expected_names = {f"GIT_CONFIG_{kind}_{index}" for index in range(count)
                      for kind in ("KEY", "VALUE")}
    if runtime_names != expected_names:
        raise CommitRefusal("runtime Git configuration pairs do not match the declared count")
    for index in range(count):
        if env[f"GIT_CONFIG_KEY_{index}"] != "safe.directory":
            raise CommitRefusal("runtime Git configuration accepts only safe.directory trust settings")
        value = env[f"GIT_CONFIG_VALUE_{index}"]
        if len(value.encode("utf-8")) > 32768 or "\0" in value:
            raise CommitRefusal("runtime Git configuration trust value exceeds finite shape")
    return env


def _git(root: Path, *args: str, input_bytes: bytes | None = None,
         allowed_codes: tuple[int, ...] = (0,)) -> bytes:
    env = _validated_git_environment()
    env.update(GIT_NO_REPLACE_OBJECTS="1", GIT_NO_LAZY_FETCH="1",
               GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0")
    result = subprocess.run(
        ["git", *args], cwd=root, input=input_bytes, capture_output=True,
        env=env, timeout=30, check=False,
    )
    if result.returncode not in allowed_codes:
        raise CommitRefusal(
            f"git {args[0]} failed ({result.returncode}): "
            + result.stderr.decode("utf-8", errors="replace")[:2000].strip()
        )
    return result.stdout


def _line(root: Path, *args: str, allowed_codes: tuple[int, ...] = (0,)) -> str:
    return _git(root, *args, allowed_codes=allowed_codes).decode("utf-8").strip()


def _git_path(root: Path, name: str) -> Path:
    path = Path(_line(root, "rev-parse", "--git-path", name))
    return path if path.is_absolute() else root / path


def _index_digest(index: Path) -> str:
    if index.is_symlink() or not index.is_file():
        raise CommitRefusal("index must be an existing regular file")
    if index.stat().st_size > MAX_INDEX_BYTES:
        raise CommitRefusal("index exceeds the supported finite size")
    data = index.read_bytes()
    if len(data) > MAX_INDEX_BYTES:
        raise CommitRefusal("index grew beyond the supported finite size")
    return hashlib.sha256(data).hexdigest()


@contextmanager
def _index_lock(index: Path, process_state: dict[str, bool] | None = None) -> Iterator[Callable[[], None]]:
    lock = index.with_name(index.name + ".lock")
    token = ("AIDE managed commit " + uuid.uuid4().hex + "\n").encode("ascii")
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0), 0o600)
    except FileExistsError as exc:
        raise CommitRefusal("index lock already exists; preserve its ownership") from exc
    identity = os.fstat(fd)
    def verify_ownership() -> None:
        try:
            observed = lock.stat()
            if ((observed.st_dev, observed.st_ino) != (identity.st_dev, identity.st_ino)
                    or observed.st_size != len(token) or lock.read_bytes() != token):
                raise CommitRefusal("owned index lock changed; preserved for recovery")
        except FileNotFoundError as exc:
            raise CommitRefusal("owned index lock disappeared; reconcile ownership") from exc
    try:
        if os.write(fd, token) != len(token):
            raise OSError("owned index lock write was incomplete")
        yield verify_ownership
    finally:
        os.close(fd)
        verify_ownership()
        if process_state is not None and not process_state["reaped"]:
            raise CommitRefusal("Git child reaping unproven; owned index lock preserved for recovery")
        lock.unlink()


def _inspect(root: Path, expected_ref: str, expected_head: str,
             expected_tree: str, allowed_paths: set[str]) -> tuple[Path, str, list[str]]:
    if Path(_line(root, "rev-parse", "--show-toplevel")).resolve() != root:
        raise CommitRefusal("repository root must name the actual checkout")
    if _line(root, "symbolic-ref", "--quiet", "--no-recurse", "HEAD") != expected_ref:
        raise CommitRefusal("HEAD branch differs from the expected ref")
    if _line(root, "symbolic-ref", "--quiet", "--no-recurse", expected_ref,
             allowed_codes=(0, 1)):
        raise CommitRefusal("expected branch must be a direct ref")
    if _line(root, "rev-parse", "--verify", "HEAD") != expected_head:
        raise CommitRefusal("HEAD differs from the expected parent")
    if _line(root, "cat-file", "-t", expected_tree) != "tree":
        raise CommitRefusal("expected tree is not a tree object")
    for operation in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD",
                      "rebase-merge", "rebase-apply", "sequencer"):
        if _git_path(root, operation).exists():
            raise CommitRefusal("non-normal Git operation is in progress: " + operation)
    if _line(root, "config", "--bool", "--get", "commit.gpgsign",
             allowed_codes=(0, 1)) == "true":
        raise CommitRefusal("configured commit signing needs a separately supported path")
    if _line(root, "config", "--get", "core.fsmonitor",
             allowed_codes=(0, 1)) not in ("", "false"):
        raise CommitRefusal("configured fsmonitor needs a separately supported path")
    for name in COMMIT_HOOKS:
        if _git_path(root, "hooks/" + name).exists():
            raise CommitRefusal("active Git hook needs a separately supported path: " + name)
    if _git(root, "ls-files", "--unmerged", "-z"):
        raise CommitRefusal("index has unresolved entries")
    try:
        _git(root, "diff", "--cached", "--no-ext-diff", "--no-textconv",
             "--ignore-submodules=none", "--quiet", expected_tree, "--")
    except CommitRefusal as exc:
        raise CommitRefusal("cannot verify the expected staged tree: " + str(exc)) from exc
    raw = _git(root, "diff", "--cached", "--no-ext-diff", "--no-textconv",
               "--ignore-submodules=none", "--name-only", "--no-renames", "-z", expected_head, "--")
    paths = [p.decode("utf-8") for p in raw.split(b"\0") if p]
    if not paths:
        raise CommitRefusal("no staged changes; empty commits are outside this path")
    if len(paths) > MAX_PATHS or not set(paths).issubset(allowed_paths):
        raise CommitRefusal("staged paths exceed the declared finite scope")
    index = _git_path(root, "index")
    return index, _index_digest(index), paths


def _verify_object(root: Path, candidate: str, tree: str, parent: str,
                   message: bytes, validator: Callable[[str], list[str]]) -> None:
    raw = _git(root, "cat-file", "commit", candidate)
    headers, body = raw.split(b"\n\n", 1)
    lines = headers.decode("utf-8").splitlines()
    trees = [s[5:] for s in lines if s.startswith("tree ")]
    parents = [s[7:] for s in lines if s.startswith("parent ")]
    if trees != [tree] or parents != [parent] or body != message:
        raise CommitRefusal("created commit object differs from frozen tree/parents/message")
    failures = validator(body.decode("utf-8"))
    if failures:
        raise CommitRefusal("created message failed strict checks: " + "; ".join(failures))


def _prepared_inputs(root: Path, expected_ref: str, expected_head: str,
                     index: Path, digest: str, verify_lock: Callable[[], None]) -> None:
    # update HEAD (without no-deref) locks HEAD and its current referent. Check
    # the exact branch while those Git locks remain held, before sending commit.
    if (_line(root, "symbolic-ref", "--quiet", "--no-recurse", "HEAD") != expected_ref
            or _line(root, "symbolic-ref", "--quiet", "--no-recurse", expected_ref,
                     allowed_codes=(0, 1))
            or _line(root, "rev-parse", "--verify", expected_ref) != expected_head
            or _index_digest(index) != digest):
        raise CommitRefusal("prepared branch or staged inputs differ from the expected subject")
    verify_lock()


def _advance_ref(root: Path, candidate: str, parent: str,
                 verify_prepared: Callable[[], None], process_state: dict[str, bool]) -> None:
    env = _validated_git_environment()
    env.update(GIT_NO_REPLACE_OBJECTS="1", GIT_NO_LAZY_FETCH="1",
               GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0")
    process = subprocess.Popen(
        ["git", "update-ref", "-m", "AIDE guarded commit", "--stdin"],
        cwd=root, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    process_state["reaped"] = False
    prepared = queue.Queue(maxsize=1)
    def read_acknowledgments() -> None:
        try:
            prepared.put([process.stdout.readline(1024).rstrip(b"\r\n") for _ in range(2)])
        except OSError as exc:
            prepared.put(exc)
    reader = threading.Thread(target=read_acknowledgments, daemon=True)
    try:
        process.stdin.write(("start\nupdate HEAD " + candidate + " " + parent
                             + "\nprepare\n").encode("ascii"))
        process.stdin.flush()
        reader.start()
        try:
            acknowledgments = prepared.get(timeout=30)
        except queue.Empty as exc:
            raise subprocess.TimeoutExpired("git update-ref prepare", 30) from exc
        reader.join(timeout=1)
        if isinstance(acknowledgments, OSError):
            raise acknowledgments
        if acknowledgments != [b"start: ok", b"prepare: ok"]:
            _, error = process.communicate(timeout=30)
            raise CommitRefusal("Git ref preparation refused: "
                                + error.decode("utf-8", errors="replace")[:2000].strip())
        try:
            verify_prepared()
        except (CommitRefusal, OSError, ValueError, subprocess.TimeoutExpired):
            process.communicate(input=b"abort\n", timeout=30)
            raise
        output, error = process.communicate(input=b"commit\n", timeout=30)
        if process.returncode != 0 or output.rstrip(b"\r\n") != b"commit: ok":
            raise CommitRefusal("Git ref commit result requires reconciliation: "
                                + error.decode("utf-8", errors="replace")[:2000].strip())
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=30)
        process_state["reaped"] = True
        if reader.ident is not None:
            reader.join(timeout=1)
        for stream in (process.stdin, process.stdout, process.stderr):
            stream.close()


def create_commit(
    root: Path, *, message: bytes, expected_message_sha256: str,
    expected_ref: str, expected_head: str, expected_tree: str,
    allowed_paths: list[str], validator: Callable[[str], list[str]],
    apply: bool = False,
) -> dict[str, object]:
    """Return a bounded outcome; never retry, reset, amend, sign or publish."""
    candidate = ""
    advanced = False
    phase = "preflight"
    outcome: dict[str, object] = {
        "status": "REFUSED", "branch_advanced": False, "candidate_commit": "",
        "expected_ref": expected_ref, "expected_head": expected_head,
        "expected_tree": expected_tree, "message_sha256": expected_message_sha256,
        "apply": apply,
    }
    try:
        root = root.resolve(strict=True)
        _validated_git_environment()
        if (len(message) > MAX_MESSAGE_BYTES or b"\0" in message or b"\r" in message
                or not message.endswith(b"\n")):
            raise CommitRefusal("message must be bounded UTF-8 LF text with a final newline")
        if hashlib.sha256(message).hexdigest() != expected_message_sha256:
            raise CommitRefusal("message differs from the expected digest")
        failures = validator(message.decode("utf-8"))
        if failures:
            raise CommitRefusal("message failed strict checks: " + "; ".join(failures))
        if not all(re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", oid)
                   for oid in (expected_head, expected_tree)):
            raise CommitRefusal("expected head/tree must be full object identities")
        if not expected_ref.startswith("refs/heads/"):
            raise CommitRefusal("expected ref must be an existing local branch")
        _git(root, "check-ref-format", expected_ref)
        if not allowed_paths or len(allowed_paths) > MAX_PATHS:
            raise CommitRefusal("declare a finite nonempty staged path scope")
        for path in allowed_paths:
            if (not isinstance(path, str) or not path or "\\" in path or ":" in path
                    or path.startswith("/") or any(p in ("", ".", "..") for p in path.split("/"))):
                raise CommitRefusal("scope paths must be exact checkout-relative paths")
        scope = set(allowed_paths)
        index = _git_path(root, "index")
        if index.with_name(index.name + ".lock").exists():
            raise CommitRefusal("index lock already exists; preserve its ownership")
        if not apply:
            _, digest, paths = _inspect(root, expected_ref, expected_head, expected_tree, scope)
            outcome.update(status="DRY_RUN", index_sha256=digest, staged_paths=paths)
            return outcome
        process_state = {"reaped": True}
        with _index_lock(index, process_state) as verify_lock:
            _, digest, paths = _inspect(root, expected_ref, expected_head, expected_tree, scope)
            phase = "candidate_object"
            candidate = _git(
                root, "commit-tree", expected_tree, "-p", expected_head,
                input_bytes=message,
            ).decode("ascii").strip()
            _verify_object(root, candidate, expected_tree, expected_head, message, validator)
            _, current_digest, current_paths = _inspect(
                root, expected_ref, expected_head, expected_tree, scope)
            if current_digest != digest or current_paths != paths:
                raise CommitRefusal("locked staged inputs changed before branch advancement")
            verify_lock()
            phase = "ref_transaction"
            _advance_ref(root, candidate, expected_head, lambda: _prepared_inputs(
                root, expected_ref, expected_head, index, digest, verify_lock), process_state)
            advanced = True
            phase = "postconditions"
            if (_line(root, "symbolic-ref", "--quiet", "--no-recurse", "HEAD") != expected_ref
                    or _line(root, "rev-parse", "--verify", expected_ref) != candidate
                    or _index_digest(index) != digest):
                raise CommitRefusal("postconditions changed; reconcile candidate/ref without replay")
            _verify_object(root, candidate, expected_tree, expected_head, message, validator)
            outcome.update(status="COMMITTED", branch_advanced=True,
                           candidate_commit=candidate, index_sha256=digest, staged_paths=paths)
            return outcome
    except (CommitRefusal, OSError, UnicodeError, ValueError, subprocess.TimeoutExpired) as exc:
        outcome.update(status="UNCERTAIN" if advanced or phase == "ref_transaction" else "REFUSED",
                       branch_advanced=(True if advanced else None if phase == "ref_transaction" else False),
                       candidate_commit=candidate,
                       phase=phase, reason=str(exc))
        return outcome
