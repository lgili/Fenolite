# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Fetch the official KiCad footprint and symbol libraries at their pinned commits into a verified cache.

    uv run python tools/kicad_libs_fetch.py [--cache DIR] [--tag TAG ...] [--repo REPO ...]
                                            [--pins PATH] [--verify]
    uv run python tools/kicad_libs_fetch.py --print-pin --tag TAG --repo REPO --commit SHA
    uv run python tools/kicad_libs_fetch.py --models PATH [PATH ...] [--cache DIR] [--tag TAG ...]
                                            [--pins PATH] [--verify]

Each pinned tree lands in <cache>/<tag>/<repo>/, where <cache> is --cache, else FENOLITE_LIBS_CACHE,
else ~/.cache/fenolite/libs. The libraries are CC-BY-SA 4.0 as a collection: they stay in the cache and
are never committed. Rules and facts: docs/formats/kicad/libraries.md, "Library cache".

One line is printed per selected folder, ending in fetched, cached, verified or failed. Exit codes: 0
nothing failed; 2 usage or environment; 3 bad input (download error, refused archive member); 5 a tree
that differs from its pin. Run one fetch at a time: there is no lock.

With --models (change c0116) no archive is downloaded. The tool reads the 3D model paths that the given
boards or footprint files name as ${KICAD<N>_3DMODEL_DIR}/<rel> and fetches each file by itself into
<cache>/<tag>/kicad-packages3D/<rel>, at the commit of the model pin of major N: it asks GitLab's files
API for the file's size and SHA-256, downloads the raw file, and keeps it only when both agree. The
official 3D models are CC-BY-SA 4.0 with the library exception, like the other libraries: they stay in
the cache. One line is printed per model path, ending in fetched, cached, skipped or failed.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from fenolite.backends.kicad import libcache  # noqa: E402
from fenolite.backends.kicad.libcache import LibraryPin, ModelPin  # noqa: E402

MAX_ARCHIVE_BYTES = 1 << 30
MAX_TREE_BYTES = 4 << 30
MAX_MODEL_BYTES = 64 << 20
"""The largest single 3D model file that --models fetches (64 MiB)."""
FILES_API = "https://gitlab.com/api/v4/projects/{project}/repository/files/{path}"
"""GitLab's files API for one file of a repository (S-0701): ``HEAD <url>?ref=<commit>`` gives its size and
SHA-256 in headers, ``GET <url>/raw?ref=<commit>`` its bytes."""
SIZE_HEADER, SHA_HEADER = "x-gitlab-size", "x-gitlab-content-sha256"
_MODEL = re.compile(r'\(model\s+"((?:[^"\\]|\\.)*)"')
_OFFICIAL = re.compile(r"^\$\{KICAD(\d+)_3DMODEL_DIR\}[/\\](.+)$")
TIMEOUT_SECONDS = 60
CHUNK = 1 << 20
USER_AGENT = "fenolite-libs-fetch (+https://github.com/lgili/Fenolite)"
EXIT_OK, EXIT_USAGE, EXIT_INPUT, EXIT_FINDINGS = 0, 2, 3, 5


class FetchError(Exception):
    """A pin that could not be fetched: ``code`` is the exit code, the message the reason."""

    def __init__(self, code: int, reason: str) -> None:
        self.code = code
        super().__init__(reason)


def archive_url(template: str, project: str, commit: str) -> str:
    return template.format(project=urllib.parse.quote(project, safe=""), commit=commit)


def head(url: str) -> dict[str, str]:
    """The response headers of ``HEAD url``, their names in lower case."""
    if urllib.parse.urlparse(url).scheme != "https":
        raise FetchError(EXIT_INPUT, "unsupported URL scheme (use https)")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310 (scheme checked)
            return {name.lower(): value for name, value in response.headers.items()}
    except Exception as exc:  # a network error is reported, not raised
        raise FetchError(EXIT_INPUT, f"request failed: {exc}") from exc


def download(url: str, target: Path, limit: int = MAX_ARCHIVE_BYTES) -> int:
    """Download ``url`` into ``target`` in 1 MiB reads; refuse more than ``limit`` bytes."""
    scheme = urllib.parse.urlparse(url).scheme
    if scheme not in ("https", "file"):
        raise FetchError(EXIT_INPUT, f"unsupported URL scheme {scheme!r} (use https or file)")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    size = 0
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310 (scheme checked)
            with target.open("wb") as out:
                while chunk := response.read(CHUNK):
                    size += len(chunk)
                    if size > limit:
                        raise FetchError(EXIT_INPUT, f"archive larger than {limit} bytes")
                    out.write(chunk)
    except FetchError:
        raise
    except Exception as exc:  # a network or file error is reported, not raised
        raise FetchError(EXIT_INPUT, f"download failed: {exc}") from exc
    return size


def extract(archive: Path, into: Path) -> Path:
    """Extract ``archive`` with the ``data`` filter and return its one top-level folder."""
    try:
        with tarfile.open(archive) as tar:
            total = 0
            for member in tar:
                if member.issym() or member.islnk():
                    raise FetchError(EXIT_INPUT, f"archive holds a link: {member.name}")
                total += member.size
                if total > MAX_TREE_BYTES:
                    raise FetchError(EXIT_INPUT, f"tree larger than {MAX_TREE_BYTES} bytes")
            tar.extractall(into, filter="data")
    except FetchError:
        raise
    except (tarfile.TarError, OSError) as exc:  # FilterError is a TarError: an unsafe member
        raise FetchError(EXIT_INPUT, f"archive refused: {exc}") from exc
    top = sorted(into.iterdir())
    if len(top) != 1 or not top[0].is_dir() or top[0].is_symlink():
        raise FetchError(EXIT_INPUT, "the archive must hold exactly one top-level folder")
    return top[0]


def fetch_tree(url: str, work: Path) -> tuple[Path, str, int, int]:
    """Download and extract into temporary entries under ``work``; the caller removes them.

    Returns the extracted top-level folder, its tree hash, its file count and the archive size.
    """
    handle, name = tempfile.mkstemp(dir=work, prefix=".archive-", suffix=".tar.gz")
    os.close(handle)
    size = download(url, Path(name))
    top = extract(Path(name), Path(tempfile.mkdtemp(dir=work, prefix=".extract-")))
    try:
        digest, files = libcache.tree_hash(top)
    except ValueError as exc:
        raise FetchError(EXIT_INPUT, str(exc)) from exc
    return top, digest, files, size


def _clean(work: Path) -> None:
    for entry in work.glob(".archive-*"):
        entry.unlink(missing_ok=True)
    for entry in (*work.glob(".extract-*"), *work.glob(".old-*")):
        shutil.rmtree(entry, ignore_errors=True)


def install(top: Path, target: Path, pin: LibraryPin) -> None:
    """Stamp ``top`` and move it to ``target``; an older folder is moved aside first and removed after."""
    libcache.write_stamp(top, pin)
    aside: Path | None = None
    if target.exists():
        aside = Path(tempfile.mkdtemp(dir=target.parent, prefix=".old-")) / target.name
        os.replace(target, aside)
    try:
        os.replace(top, target)
    except OSError:
        if aside is not None:
            os.replace(aside, target)
        raise
    if aside is not None:
        shutil.rmtree(aside.parent, ignore_errors=True)


def fetch_pin(pin: LibraryPin, cache: Path, template: str, *, verify: bool) -> str:
    """``fetched``, ``cached`` or ``verified``; ``FetchError`` otherwise. The cache is left as it was on a
    failure."""
    target = cache / pin.tag / pin.repo
    if libcache.stamp_matches(target, pin):
        if not verify:
            return "cached"
        digest, files = libcache.tree_hash(target)
        if (digest, files) != (pin.tree, pin.files):
            raise FetchError(EXIT_FINDINGS, f"{target} differs from its pin (tree {digest}, {files} files)")
        return "verified"
    work = cache / pin.tag
    work.mkdir(parents=True, exist_ok=True)
    try:
        top, digest, files, _ = fetch_tree(archive_url(template, pin.project, pin.commit), work)
        if (digest, files) != (pin.tree, pin.files):
            raise FetchError(EXIT_FINDINGS, f"tree {digest} with {files} files differs from the pin")
        install(top, target, pin)
    except OSError as exc:
        raise FetchError(EXIT_INPUT, f"cache not written: {exc}") from exc
    finally:
        _clean(work)
    return "fetched"


def print_pin(tag: str, repo: str, commit: str, cache: Path, template: str) -> int:
    """Download and hash the archive of ``commit`` and print its pin as TOML; the cache stays as it was."""
    work = Path(tempfile.mkdtemp(prefix="fenolite-libs-pin-"))
    try:
        project = f"kicad/libraries/{repo}"
        _, digest, files, size = fetch_tree(archive_url(template, project, commit), work)
    except FetchError as error:
        print(f"{tag}/{repo}: failed ({error})", file=sys.stderr)
        return error.code
    finally:
        shutil.rmtree(work, ignore_errors=True)
    major = tag.split(".", 1)[0]
    print(
        f'[[pin]]\ntag = "{tag}"\nmajor = {major}\nrepo = "{repo}"\nproject = "{project}"\n'
        f'commit = "{commit}"\ntree = "{digest}"\nfiles = {files}\n# archive: {size} bytes'
    )
    return EXIT_OK


# --- 3D models, one file at a time (change c0116) ------------------------------------------------------


def model_paths(sources: list[Path]) -> list[str]:
    """Every distinct ``(model "<path>" …)`` path that the boards or footprint files name, sorted."""
    found: set[str] = set()
    for source in sources:
        try:
            text = source.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise FetchError(EXIT_INPUT, f"cannot read {source.name}: {exc.strerror or exc}") from exc
        found.update(
            match.group(1).replace('\\"', '"').replace("\\\\", "\\") for match in _MODEL.finditer(text)
        )
    return sorted(found)


def _official(path: str) -> tuple[int, str] | None:
    """``(N, <rel>)`` of ``${KICAD<N>_3DMODEL_DIR}/<rel>``; ``None`` for any other path, or a ``<rel>``
    that would leave its folder."""
    match = _OFFICIAL.match(path)
    if match is None:
        return None
    parts = match.group(2).replace("\\", "/").split("/")
    if not all(parts) or ".." in parts or "." in parts:
        return None
    return int(match.group(1)), "/".join(parts)


def file_url(pin: ModelPin, rel: str, *, raw: bool = False) -> str:
    url = FILES_API.format(
        project=urllib.parse.quote(pin.project, safe=""), path=urllib.parse.quote(rel, safe="")
    )
    return f"{url}{'/raw' if raw else ''}?ref={pin.commit}"


def _sha256(path: Path) -> str:
    return libcache.file_sha256(path)


def fetch_model(pin: ModelPin, rel: str, cache: Path) -> str:
    """``fetched`` or ``cached``; ``FetchError`` otherwise, with the target and the stamp left as they
    were and no temporary file left behind."""
    folder = cache / pin.tag / libcache.MODEL_REPO
    target = folder / rel
    stamp = libcache.read_model_stamp(folder)
    if rel in stamp and target.is_file() and _sha256(target) == stamp[rel]:
        return "cached"
    headers = head(file_url(pin, rel))
    announced, digest = headers.get(SIZE_HEADER, ""), headers.get(SHA_HEADER, "").lower()
    if not announced.isdigit() or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise FetchError(EXIT_INPUT, "the files API gave no size and SHA-256 for the file")
    if int(announced) > MAX_MODEL_BYTES:
        raise FetchError(EXIT_INPUT, f"{announced} bytes, more than {MAX_MODEL_BYTES}")
    work = cache / pin.tag
    try:
        work.mkdir(parents=True, exist_ok=True)
        handle, name = tempfile.mkstemp(dir=work, prefix=".model-", suffix=".part")
        os.close(handle)
    except OSError as exc:
        raise FetchError(EXIT_INPUT, f"cache not written: {exc}") from exc
    partial = Path(name)
    try:
        size = download(file_url(pin, rel, raw=True), partial, MAX_MODEL_BYTES)
        found = _sha256(partial)
        if size != int(announced) or found != digest:
            raise FetchError(
                EXIT_FINDINGS,
                f"{size} bytes with SHA-256 {found} differ from the announced {announced} bytes and {digest}",
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(partial, target)
        libcache.write_model_stamp(folder, {**libcache.read_model_stamp(folder), rel: digest})
    except OSError as exc:
        raise FetchError(EXIT_INPUT, f"cache not written: {exc}") from exc
    finally:
        partial.unlink(missing_ok=True)
    return "fetched"


def verify_models(pins: list[ModelPin], cache: Path) -> int:
    """Re-hash every stamped model file of ``pins``; one line and exit 5 for each that differs."""
    worst = EXIT_OK
    for pin in pins:
        folder = cache / pin.tag / libcache.MODEL_REPO
        for rel, digest in sorted(libcache.read_model_stamp(folder).items()):
            file = folder / rel
            if not file.is_file() or _sha256(file) != digest:
                print(f"{pin.tag}/{libcache.MODEL_REPO}/{rel}: failed (differs from its stamp entry)")
                worst = EXIT_FINDINGS
    return worst


def fetch_models(sources: list[Path], cache: Path, pins: list[ModelPin], *, verify: bool) -> int:
    """The --models mode: one line per model path of ``sources``; the worst exit code of the files."""
    by_major = {pin.major: pin for pin in pins}
    worst = EXIT_OK
    try:
        paths = model_paths(sources)
    except FetchError as error:
        print(f"failed ({error})", file=sys.stderr)
        return error.code
    for path in paths:
        named = _official(path)
        pin = by_major.get(named[0]) if named is not None else None
        if named is None or pin is None:
            print(f"{path}: skipped")
            continue
        try:
            print(f"{path}: {fetch_model(pin, named[1], cache)}")
        except FetchError as error:
            print(f"{path}: failed ({error})")
            worst = max(worst, error.code)
    if verify:
        worst = max(worst, verify_models(pins, cache))
    return worst


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch and verify the official KiCad libraries.")
    parser.add_argument("--cache", type=Path, default=None, help="cache folder")
    parser.add_argument("--tag", action="append", default=[], metavar="TAG", help="only this tag")
    parser.add_argument("--repo", action="append", default=[], metavar="REPO", help="only this repository")
    parser.add_argument("--pins", type=Path, default=None, help="a pins file instead of the package's")
    parser.add_argument("--verify", action="store_true", help="re-hash the cached folders")
    parser.add_argument("--print-pin", action="store_true", help="print the pin of --tag --repo --commit")
    parser.add_argument("--commit", default=None, metavar="SHA", help="the commit of --print-pin")
    parser.add_argument(
        "--models",
        nargs="*",
        type=Path,
        default=None,
        metavar="PATH",
        help="fetch the official 3D models these boards or footprint files name, one file at a time",
    )
    try:
        args = parser.parse_args(argv)
    except SystemExit as stop:
        return EXIT_USAGE if stop.code else EXIT_OK
    if not hasattr(tarfile, "data_filter"):
        print("the tarfile data filter is missing: Python 3.11.4 or newer is needed", file=sys.stderr)
        return EXIT_USAGE
    cache = args.cache or libcache.default_cache_dir()
    try:
        template = libcache.archive_template(args.pins)
    except (OSError, ValueError) as exc:
        print(f"pins file: {exc}", file=sys.stderr)
        return EXIT_USAGE
    if args.models is not None:
        if args.print_pin or args.repo or not (args.models or args.verify):
            print("--models needs a board or footprint file (or --verify), and no --repo", file=sys.stderr)
            return EXIT_USAGE
        try:
            model_pins = [p for p in libcache.load_model_pins(args.pins) if not args.tag or p.tag in args.tag]
        except (OSError, ValueError) as exc:
            print(f"pins file: {exc}", file=sys.stderr)
            return EXIT_USAGE
        if not model_pins:
            print("no model pin matches --tag", file=sys.stderr)
            return EXIT_USAGE
        return fetch_models(list(args.models), cache, model_pins, verify=args.verify)
    if args.print_pin:
        if len(args.tag) != 1 or len(args.repo) != 1 or not args.commit or args.repo[0] not in libcache.REPOS:
            print("--print-pin needs one --tag, one --repo and --commit", file=sys.stderr)
            return EXIT_USAGE
        return print_pin(args.tag[0], args.repo[0], args.commit, cache, template)
    try:
        pins = libcache.load_pins(args.pins)
    except (OSError, ValueError) as exc:
        print(f"pins file: {exc}", file=sys.stderr)
        return EXIT_USAGE
    selected = [
        p for p in pins if (not args.tag or p.tag in args.tag) and (not args.repo or p.repo in args.repo)
    ]
    if not selected:
        print("no pin matches --tag and --repo", file=sys.stderr)
        return EXIT_USAGE
    worst = EXIT_OK
    for pin in selected:
        try:
            print(f"{pin.tag}/{pin.repo}: {fetch_pin(pin, cache, template, verify=args.verify)}")
        except FetchError as error:
            print(f"{pin.tag}/{pin.repo}: failed ({error})")
            worst = max(worst, error.code)
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
