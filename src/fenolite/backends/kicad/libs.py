# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad library identifiers, library tables, path variables, library sources and the resolver.

Facts, the Fenolite choices and their labels: ``docs/formats/kicad/libraries.md``. Every file system
and operating-system input comes from ``LibraryConfig`` (or its defaults), so tests stay hermetic.
Errors are raised as ``LibraryError``; warnings and infos go to ``LibraryResolver.issues`` (tables)
or to the ``issues`` list a lookup is given (readers).
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from fenolite.backends.kicad import libcache, versions
from fenolite.backends.kicad._libread import Loaded, child_locators, load_source
from fenolite.backends.kicad.liberrors import LibraryError, lib_error, lib_issue
from fenolite.backends.kicad.mod import footprint_from
from fenolite.backends.kicad.sexpr import AtomKind, Node, parse
from fenolite.backends.kicad.sym import resolve_extends, symbols_from
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.library import FootprintDef, SymbolDef

EVIDENCE = Evidence(
    Level.INFERRED,
    hypotheses=(
        "H-K-LIB-COMMON",
        "H-K-LIB-CONFIGHOME",
        "H-K-LIB-FALLBACK",
        "H-K-LIB-NESTED",
        "H-K-LIB-RELPATH-2",
        "H-K-LIB-SCAN",
    ),
)
"""Reading library tables and resolving their rows: ``INFERRED``, the level of ``H-K-LIB-SCAN``; the
other rows hold for the cases their tests ran, on the majors they name (declared by change c0067)."""
WRITE_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-BUILD-LIBTABLE",))
"""``write_lib_table``: ``kicad-cli`` reads the tables that the build oracle wrote, not every table."""
TableKind = Literal["footprint", "symbol"]
RowOrigin = Literal["project", "global", "template", "scan"]
SourceKind = Literal["env", "cache", "install"]

TABLE_FILES: Mapping[TableKind, str] = {"footprint": "fp-lib-table", "symbol": "sym-lib-table"}
TABLE_ROOTS: Mapping[str, TableKind] = {"fp_lib_table": "footprint", "sym_lib_table": "symbol"}
SUPPORTED_TYPES = ("KiCad", "Table")
LIBRARY_VARIABLES = ("FOOTPRINT_DIR", "SYMBOL_DIR", "3DMODEL_DIR", "TEMPLATE_DIR")
_INSTALL_DIRS = {"FOOTPRINT_DIR": "footprints", "SYMBOL_DIR": "symbols", "3DMODEL_DIR": "3dmodels"}
_VARIABLE = re.compile(r"\$\{([^}]*)\}")
_VERSIONED = re.compile(r"KICAD(\d+)_(\w+)")
_HEADER_VERSION = re.compile(rb"\(version\s+(\d+)\)")
_ROW_FIELDS = ("name", "type", "uri", "options", "descr")
CACHE_SIZE = 16
COMMON_FILE = "kicad_common.json"
"""KiCad's own settings file in ``<config>/<M>.0/``; its ``environment.vars`` object holds the path
variables set in KiCad (observed, ``H-K-LIB-COMMON``). Read only with ``LibraryConfig.read_common``."""
_SCAN_VARIABLE: Mapping[TableKind, str] = {"footprint": "FOOTPRINT_DIR", "symbol": "SYMBOL_DIR"}
_CACHE_DIRS = {"FOOTPRINT_DIR": "kicad-footprints", "SYMBOL_DIR": "kicad-symbols"}
MACOS_INSTALL = Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport")
LINUX_INSTALL = Path("/usr/share/kicad")


def split_lib_id(lib_id: str) -> tuple[str, str]:
    """``"Device:R"`` -> ``("Device", "R")``; anything else raises ``kicad.lib.invalid-id``."""
    nickname, sep, entry = lib_id.partition(":")
    if not sep or not nickname or not entry or ":" in entry:
        raise lib_error(
            "kicad.lib.invalid-id",
            f"{lib_id!r} is not a library identifier 'NICKNAME:ENTRY'",
            where=lib_id,
            hint="write the nickname of a library table row, a colon and the item name",
        )
    return nickname, entry


@dataclass(frozen=True, slots=True)
class LibRow:
    """One ``(lib …)`` row of a library table, values as written (variables unexpanded)."""

    nickname: str
    type: str
    uri: str
    options: str = ""
    descr: str = ""
    disabled: bool = False
    hidden: bool = False


@dataclass(frozen=True, slots=True)
class LibTable:
    kind: TableKind
    rows: tuple[LibRow, ...]
    version: int | None = None
    path: str = ""


def _flag(node: Node) -> bool:
    values = [a.value for a in node.atoms()]
    return values != ["no"]


def _row(node: Node, loc: str, file: str, issues: list[Issue]) -> LibRow:
    values: dict[str, str] = {}
    flags = {"disabled": False, "hidden": False}
    for child_loc, child in child_locators(loc, node):
        if not isinstance(child, Node):
            issues.append(
                lib_issue("kicad.lib.kept-opaque", "atom in a library row ignored", where=child_loc)
            )
        elif child.name in _ROW_FIELDS:
            values[child.name] = " ".join(a.value for a in child.atoms())
        elif child.name in flags:
            flags[child.name] = _flag(child)
        else:
            issues.append(
                lib_issue(
                    "kicad.lib.kept-opaque",
                    f"unknown library row child {child.name!r} ignored",
                    where=child_loc,
                )
            )
    for required in ("name", "type", "uri"):
        if required not in values:
            raise FormatError(f"library row has no {required!r}", file=file, locator=loc, offset=node.offset)
    return LibRow(
        values["name"],
        values["type"],
        values["uri"],
        values.get("options", ""),
        values.get("descr", ""),
        flags["disabled"],
        flags["hidden"],
    )


def read_lib_table(
    source: str | os.PathLike[str], *, file: str = "", issues: list[Issue] | None = None
) -> LibTable:
    """An ``fp-lib-table`` or ``sym-lib-table`` from a path or file text, in either syntax."""
    sink = issues if issues is not None else []
    path = ""
    if isinstance(source, str):
        root = parse(source, file=file)
    else:
        path = os.fspath(source)
        file = file or path
        root = parse(Path(path).read_text(encoding="utf-8"), file=file)
    kind = TABLE_ROOTS.get(root.name)
    if kind is None:
        raise FormatError(
            f"unknown library table root {root.name!r} (expected fp_lib_table or sym_lib_table)",
            file=file,
            locator=f"/{root.name}",
            offset=root.offset,
        )
    version: int | None = None
    rows: list[LibRow] = []
    seen: set[str] = set()
    for loc, child in child_locators(f"/{root.name}", root):
        if not isinstance(child, Node):
            sink.append(lib_issue("kicad.lib.kept-opaque", "atom in a library table ignored", where=loc))
        elif child.name == "version":
            atoms = child.atoms()
            if len(atoms) != 1 or atoms[0].kind != AtomKind.NUMBER or not atoms[0].text.isdigit():
                raise FormatError(
                    "table version must be an integer", file=file, locator=loc, offset=child.offset
                )
            version = int(atoms[0].text)
        elif child.name == "lib":
            row = _row(child, loc, file, sink)
            if row.nickname in seen:
                sink.append(
                    lib_issue(
                        "kicad.lib.duplicate-nickname",
                        f"second row with nickname {row.nickname!r} ignored (the first row is kept)",
                        where=f"{file}:{loc}" if file else loc,
                    )
                )
                continue
            seen.add(row.nickname)
            rows.append(row)
        else:
            sink.append(
                lib_issue("kicad.lib.kept-opaque", f"unknown table child {child.name!r} ignored", where=loc)
            )
    return LibTable(kind, tuple(rows), version, path)


@dataclass(frozen=True, slots=True)
class LibraryConfig:
    """Inputs of a resolver. ``None`` means the default named in ``docs/formats/kicad/libraries.md``.

    ``env`` defaults to a snapshot of ``os.environ``; ``system`` to ``sys.platform``; ``home`` to
    ``Path.home()``; ``install_dir`` to the per-OS install folder (a missing path means no install).
    ``cache_dir`` names a verified library cache, else ``FENOLITE_LIBS_CACHE`` of ``env`` does; no default
    location is searched. ``read_common`` turns on the path variables of KiCad's ``kicad_common.json``.
    """

    target_major: int = 10
    project_dir: Path | None = None
    env: Mapping[str, str] | None = None
    config_home: Path | None = None
    install_dir: Path | None = None
    use_global_table: bool = True
    system: str | None = None
    home: Path | None = None
    cache_dir: Path | None = None
    read_common: bool = False


@dataclass(frozen=True, slots=True)
class LibrarySource:
    """Where official libraries live: a folder named by a variable, a verified cache of one pinned tag,
    or a local install."""

    kind: SourceKind
    root: Path
    major: int


def _environment(config: LibraryConfig) -> dict[str, str]:
    return dict(config.env if config.env is not None else os.environ)


def _install_candidates(config: LibraryConfig, env: Mapping[str, str]) -> list[Path]:
    if config.install_dir is not None:
        return [config.install_dir]
    system = config.system or sys.platform
    if system.startswith("win"):
        base = Path(env.get("ProgramFiles", r"C:\Program Files")) / "KiCad"
        return [
            base / f"{major}.0" / "share" / "kicad" for major in sorted(versions.TARGET_MAJORS, reverse=True)
        ]
    return [MACOS_INSTALL] if system == "darwin" else [LINUX_INSTALL]


def _library_major(folder: Path) -> int | None:
    """The major of the first symbol library of ``folder``, from the first 4 KiB of its header."""
    candidates = sorted(folder.glob("*.kicad_sym")) or sorted(folder.glob("*.kicad_symdir/*.kicad_sym"))
    for candidate in candidates[:1]:
        with candidate.open("rb") as handle:
            match = _HEADER_VERSION.search(handle.read(4096))
        if match:
            return versions.major_for(versions.FileKind.SYMBOL_LIB, int(match.group(1)))
    return None


def _cache_dir(config: LibraryConfig, env: Mapping[str, str]) -> Path | None:
    """The cache folder asked for (``cache_dir``, else ``FENOLITE_LIBS_CACHE``), when it exists."""
    named = config.cache_dir if config.cache_dir is not None else env.get(libcache.CACHE_VARIABLE)
    if not named:
        return None
    return Path(named) if Path(named).is_dir() else None


def scan_library_folder(folder: Path, kind: TableKind, *, variable: str) -> tuple[LibRow, ...]:
    """One ``KiCad`` row per library of ``folder``, in sorted name order (the directory scan,
    ``H-K-LIB-SCAN``): ``<X>.pretty`` folders for footprints; ``<X>.kicad_sym`` files and
    ``<X>.kicad_symdir`` folders for symbols, the file winning for one stem. The uri is
    ``${<variable>}/<name>``."""
    if not folder.is_dir():
        return ()
    names: dict[str, str] = {}
    for entry in sorted(folder.iterdir(), key=lambda p: p.name):
        if kind == "footprint":
            if entry.suffix == ".pretty" and entry.is_dir():
                names[entry.stem] = entry.name
        elif entry.suffix == ".kicad_sym" and entry.is_file():
            names[entry.stem] = entry.name
        elif entry.suffix == ".kicad_symdir" and entry.is_dir():
            names.setdefault(entry.stem, entry.name)
    return tuple(LibRow(stem, "KiCad", f"${{{variable}}}/{names[stem]}") for stem in sorted(names))


def _read_common(path: Path) -> dict[str, str]:
    """The path variables of a ``kicad_common.json``: its ``environment.vars`` object.

    A missing file, a missing ``environment`` or ``vars``, or ``vars`` set to ``null`` give no variables.
    Anything else that is not an object of strings raises ``FormatError`` with the file and the JSON
    pointer. Values are returned as written.
    """
    if not path.is_file():
        return {}

    def bad(message: str, pointer: str) -> FormatError:
        return FormatError(message, file=str(path), locator=pointer)

    try:
        data: object = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise bad(f"not valid JSON: {exc}", "/") from exc
    if not isinstance(data, dict):
        raise bad("the file must hold a JSON object", "/")
    environment = cast(dict[str, object], data).get("environment")
    if environment is None:
        return {}
    if not isinstance(environment, dict):
        raise bad("'environment' must be an object", "/environment")
    values = cast(dict[str, object], environment).get("vars")
    if values is None:
        return {}
    if not isinstance(values, dict):
        raise bad("'vars' must be an object of strings or null", "/environment/vars")
    found: dict[str, str] = {}
    for name, value in cast(dict[str, object], values).items():
        if not isinstance(value, str):
            raise bad(f"the value of {name!r} must be a string", f"/environment/vars/{name}")
        found[name] = value
    return found


def find_library_sources(config: LibraryConfig) -> tuple[LibrarySource, ...]:
    """Every available source: ``env`` folders of ``KICAD9_*``/``KICAD10_*`` variables, then the verified
    ``cache`` folder of each pinned tag, then the install."""
    env = _environment(config)
    found: list[LibrarySource] = []
    for major in sorted(versions.TARGET_MAJORS, reverse=True):
        for name in ("FOOTPRINT_DIR", "SYMBOL_DIR"):
            value = env.get(f"KICAD{major}_{name}")
            if value and Path(value).is_dir():
                found.append(LibrarySource("env", Path(value), major))
    cache = _cache_dir(config, env)
    if cache is not None:
        tags: list[str] = []
        for pin, _ in libcache.verified_folders(cache):
            if pin.tag not in tags:
                tags.append(pin.tag)
                found.append(LibrarySource("cache", cache / pin.tag, pin.major))
    for root in _install_candidates(config, env):
        if root.is_dir() and (root / "symbols").is_dir():
            major = _library_major(root / "symbols")
            if major is not None:
                found.append(LibrarySource("install", root, major))
                break
    return tuple(found)


@dataclass(frozen=True, slots=True)
class Location:
    """Where a library item was found and through which row."""

    lib_id: str
    kind: TableKind
    row: LibRow
    origin: RowOrigin
    table: str
    library_path: Path
    item_path: Path


Entry = tuple[LibRow, RowOrigin, str]


class LibraryResolver:
    """Resolve library identifiers like KiCad: project, global (or template) and nested tables."""

    def __init__(self, config: LibraryConfig | None = None) -> None:
        self.config = config if config is not None else LibraryConfig()
        self.issues: list[Issue] = []
        self._env = _environment(self.config)
        self._sources: tuple[LibrarySource, ...] | None = None
        self._rows: dict[TableKind, tuple[Entry, ...]] = {}
        self._cache: OrderedDict[tuple[str, int, int], Loaded] = OrderedDict()
        self._common: dict[str, str] | None = None

    # --- variables --------------------------------------------------------------------------------

    @property
    def sources(self) -> tuple[LibrarySource, ...]:
        if self._sources is None:
            self._sources = find_library_sources(self.config)
        return self._sources

    def _source(self) -> LibrarySource | None:
        major = self.config.target_major
        ranked = [s for s in self.sources if s.major == major]
        for kind in ("env", "cache", "install"):
            found = next((s for s in ranked if s.kind == kind), None)
            if found is not None:
                return found
        return None

    def _defaults(self) -> dict[str, str]:
        source = self._source()
        major = self.config.target_major
        if source is not None and source.kind == "cache":
            # only the verified subfolders; models and templates are not fetched
            verified = {folder.name for _, folder in libcache.verified_folders(source.root.parent)}
            return {
                f"KICAD{major}_{var}": str(source.root / sub)
                for var, sub in _CACHE_DIRS.items()
                if sub in verified and libcache.read_stamp(source.root / sub) is not None
            }
        if source is None or source.kind != "install":
            return {}
        out = {f"KICAD{major}_{var}": str(source.root / sub) for var, sub in _INSTALL_DIRS.items()}
        out[f"KICAD{major}_TEMPLATE_DIR"] = str(source.root / "template")
        return out

    def _common_vars(self) -> dict[str, str]:
        """``environment.vars`` of the target major's ``kicad_common.json``, read once and only on request."""
        if not self.config.read_common:
            return {}
        if self._common is None:
            self._common = _read_common(self._config_base() / f"{self.config.target_major}.0" / COMMON_FILE)
        return self._common

    def _lookup(self, name: str) -> str | None:
        if name == "KIPRJMOD":
            project = self.config.project_dir
            return None if project is None else str(project)
        if name in self._env:
            return self._env[name]
        common = self._common_vars()
        if name in common:
            return common[name]
        defaults = self._defaults()
        if name in defaults:
            return defaults[name]
        match = _VERSIONED.fullmatch(name)
        if match and int(match.group(1)) < self.config.target_major:
            return self._lookup(f"KICAD{int(match.group(1)) + 1}_{match.group(2)}")
        return None

    def variables(self) -> dict[str, str]:
        """The values known without the fallback: ``KIPRJMOD``, the environment, KiCad's configured
        variables (on request) and the defaults."""
        out = dict(self._env)
        out.update({k: v for k, v in self._common_vars().items() if k not in out})
        out.update({k: v for k, v in self._defaults().items() if k not in out})
        if self.config.project_dir is not None:
            out["KIPRJMOD"] = str(self.config.project_dir)
        return out

    def _hint(self, name: str) -> str:
        major = self.config.target_major
        match = _VERSIONED.fullmatch(name)
        if match and match.group(2) in LIBRARY_VARIABLES:
            return (
                f"set KICAD{major}_FOOTPRINT_DIR and KICAD{major}_SYMBOL_DIR (or {name}) in the environment, "
                f"or install KiCad {major}.0"
            )
        if name == "KIPRJMOD":
            return "pass the project folder as LibraryConfig.project_dir"
        if self.config.read_common:
            return f"set {name} in the environment or in KiCad's path variables"
        return (
            f"set {name} in the environment, or read the path variables set in KiCad with "
            "LibraryConfig.read_common"
        )

    def expand(self, text: str, *, row_table: str = "") -> str:
        """``${NAME}`` replaced by its value. A relative result of a table row (``row_table`` given) is
        joined to the project folder, whatever table holds the row; without a project folder it stays
        relative, so it is read against the working directory.

        ``kicad-cli`` resolves a relative uri against its working directory, in project, nested and global
        tables alike, and never against the folder of the table (``H-K-LIB-RELPATH-2``). The project
        folder stands for the working directory of a KiCad that runs in the project, so that a result
        does not depend on where the caller runs."""

        def value(match: re.Match[str]) -> str:
            name = match.group(1)
            found = self._lookup(name)
            if found is None:
                raise lib_error(
                    "kicad.lib.unresolved-variable",
                    f"path variable {name!r} has no value (in {text!r})",
                    where=row_table or text,
                    hint=self._hint(name),
                )
            return found

        result = _VARIABLE.sub(value, text)
        if row_table and not os.path.isabs(result):
            project = self.config.project_dir
            result = os.path.normpath(os.path.join(project, result) if project is not None else result)
        return result

    def _path(self, uri: str, table: str) -> Path:
        return Path(os.path.normpath(self.expand(uri, row_table=table)))

    # --- tables -----------------------------------------------------------------------------------

    def _config_base(self) -> Path:
        if self.config.config_home is not None:
            return self.config.config_home
        if self._env.get("KICAD_CONFIG_HOME"):
            return Path(self._env["KICAD_CONFIG_HOME"])
        system = self.config.system or sys.platform
        home = self.config.home if self.config.home is not None else Path.home()
        if system.startswith("win"):
            return Path(self._env.get("APPDATA", str(home / "AppData" / "Roaming"))) / "kicad"
        if system == "darwin":
            return home / "Library" / "Preferences" / "kicad"
        return home / ".config" / "kicad"

    def _template(self, kind: TableKind) -> Path | None:
        name = TABLE_FILES[kind]
        major = self.config.target_major
        source = self._source()
        if source is not None and source.kind == "cache":
            return None  # a fetched tree is a source tree: it is scanned, never templated
        candidates: list[Path] = []
        if source is not None and source.kind == "install":
            candidates.append(source.root / "template" / name)
        folder = "FOOTPRINT_DIR" if kind == "footprint" else "SYMBOL_DIR"
        for var in (f"KICAD{major}_TEMPLATE_DIR", f"KICAD{major}_{folder}"):
            value = self._lookup(var)
            if value:
                candidates.append(Path(value) / name)
        return next((c for c in candidates if c.is_file()), None)

    def _expand_table(self, path: Path, origin: RowOrigin, out: list[Entry], stack: tuple[str, ...]) -> None:
        key = os.path.normcase(os.path.realpath(path))
        if key in stack:
            self.issues.append(
                lib_issue(
                    "kicad.lib.table-cycle",
                    f"nested table {path} is already being expanded; skipped",
                    where=str(path),
                )
            )
            return
        table = read_lib_table(path, issues=self.issues)
        for row in table.rows:
            if row.type != "Table":
                out.append((row, origin, str(path)))
                continue
            if row.disabled:
                continue
            if self.config.target_major < 10:
                self.issues.append(
                    lib_issue(
                        "kicad.lib.nested-table-target",
                        f"nested table row {row.nickname!r} is expanded, but KiCad "
                        f"{self.config.target_major}.0 does not read nested tables",
                        where=str(path),
                    )
                )
            try:
                target = self._path(row.uri, str(path))
            except LibraryError as exc:
                self.issues.append(
                    lib_issue(
                        "kicad.lib.missing-table",
                        f"nested table {row.nickname!r}: {exc.issue.message}",
                        where=str(path),
                    )
                )
                continue
            if not target.is_file():
                self.issues.append(
                    lib_issue(
                        "kicad.lib.missing-table",
                        f"nested table {row.nickname!r} not found: {target}",
                        where=str(path),
                    )
                )
                continue
            self._expand_table(target, origin, out, (*stack, key))

    def rows(self, kind: TableKind) -> tuple[Entry, ...]:
        """Effective rows ``(row, origin, table file)``, project first; a nickname hides later rows."""
        if kind in self._rows:
            return self._rows[kind]
        name = TABLE_FILES[kind]
        entries: list[Entry] = []
        if self.config.project_dir is not None and (self.config.project_dir / name).is_file():
            self._expand_table(self.config.project_dir / name, "project", entries, ())
        if self.config.use_global_table:
            global_table = self._config_base() / f"{self.config.target_major}.0" / name
            if global_table.is_file():
                self._expand_table(global_table, "global", entries, ())
            else:
                template = self._template(kind)
                if template is not None:
                    self._expand_table(template, "template", entries, ())
                else:
                    variable = f"KICAD{self.config.target_major}_{_SCAN_VARIABLE[kind]}"
                    folder = self._lookup(variable)
                    if folder:
                        for row in scan_library_folder(Path(folder), kind, variable=variable):
                            entries.append((row, "scan", folder))
        effective: list[Entry] = []
        enabled: set[str] = set()
        disabled: set[str] = set()
        for entry in entries:
            nickname = entry[0].nickname
            if nickname in enabled or (entry[0].disabled and nickname in disabled):
                continue
            (disabled if entry[0].disabled else enabled).add(nickname)
            effective.append(entry)
        self._rows[kind] = tuple(effective)
        return self._rows[kind]

    # --- lookups ----------------------------------------------------------------------------------

    def _load(self, path: Path) -> Loaded:
        stat = path.stat()
        key = (str(path), stat.st_mtime_ns, stat.st_size)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        loaded = load_source(path)
        self._cache[key] = loaded
        while len(self._cache) > CACHE_SIZE:
            self._cache.popitem(last=False)
        return loaded

    def _names(self, path: Path) -> list[str]:
        node = self._load(path).node
        return [s.atoms()[0].value for s in node.nodes("symbol") if s.atoms()]

    def _scan(self, folder: Path, entry: str) -> Path | None:
        """The file of a symbol folder holding ``entry``: ``<entry>.kicad_sym`` first, then a scan."""
        direct = folder / f"{entry}.kicad_sym"
        if direct.is_file() and entry in self._names(direct):
            return direct
        for candidate in sorted(folder.glob("*.kicad_sym")):
            if candidate != direct and candidate.is_file() and entry in self._names(candidate):
                return candidate
        return None

    def locate(self, lib_id: str, kind: TableKind) -> Location:
        nickname, entry = split_lib_id(lib_id)
        matches = [e for e in self.rows(kind) if e[0].nickname == nickname]
        usable = [e for e in matches if not e[0].disabled]
        if not matches:
            tables = sorted({e[2] for e in self.rows(kind)})
            raise lib_error(
                "kicad.lib.unknown-nickname",
                f"no {kind} library table row has the nickname {nickname!r}",
                where=lib_id,
                hint="tables searched: "
                + (", ".join(tables) if tables else "none (no project, global or template table)"),
            )
        if not usable:
            raise lib_error(
                "kicad.lib.disabled", f"{kind} library {nickname!r} is disabled", where=matches[0][2]
            )
        row, origin, table = usable[0]
        if row.type != "KiCad":
            raise lib_error(
                "kicad.lib.unsupported-type",
                f"{kind} library {nickname!r} has type {row.type!r}; Fenolite reads 'KiCad' libraries",
                where=table,
            )
        library = self._path(row.uri, table)
        if kind == "footprint":
            if not library.is_dir():
                raise lib_error(
                    "kicad.lib.missing-library",
                    f"footprint library folder {library} not found",
                    where=str(library),
                )
            item = library / f"{entry}.kicad_mod"
            if not item.is_file():
                raise lib_error(
                    "kicad.lib.missing-entry", f"footprint {entry!r} not in {library}", where=str(library)
                )
        elif library.is_dir():
            found = self._scan(library, entry)
            if found is None:
                raise lib_error(
                    "kicad.lib.missing-entry", f"symbol {entry!r} not in {library}", where=str(library)
                )
            item = found
        elif library.is_file():
            if entry not in self._names(library):
                raise lib_error(
                    "kicad.lib.missing-entry", f"symbol {entry!r} not in {library}", where=str(library)
                )
            item = library
        else:
            raise lib_error(
                "kicad.lib.missing-library", f"symbol library {library} not found", where=str(library)
            )
        return Location(lib_id, kind, row, origin, table, library, item)

    def footprint(self, lib_id: str, *, issues: list[Issue] | None = None) -> FootprintDef:
        """The footprint behind ``lib_id``, with ``library`` set to the nickname."""
        location = self.locate(lib_id, "footprint")
        return footprint_from(self._load(location.item_path), library=location.row.nickname, issues=issues)

    def symbol(self, lib_id: str, *, issues: list[Issue] | None = None) -> SymbolDef:
        """The flattened symbol behind ``lib_id``; parents are looked up in the same library."""
        location = self.locate(lib_id, "symbol")
        nickname, entry = split_lib_id(lib_id)
        symbols = {
            s.name: s for s in symbols_from(self._load(location.item_path), library=nickname, issues=issues)
        }
        chain = [symbols[entry]]
        while chain[-1].extends and chain[-1].extends not in {s.name for s in chain}:
            parent = chain[-1].extends
            if parent not in symbols and location.library_path.is_dir():
                found = self._scan(location.library_path, parent)
                if found is not None:
                    loaded = self._load(found)
                    symbols.update({s.name: s for s in symbols_from(loaded, library=nickname, issues=issues)})
            if parent not in symbols:
                break
            chain.append(symbols[parent])
        return resolve_extends(chain)[0]

    def missing_models(self, fp: FootprintDef) -> tuple[Issue, ...]:
        """One warning per 3D model path that names no file or has a variable without a value."""
        out: list[Issue] = []
        for model in fp.models:
            try:
                expanded = self.expand(model)
            except LibraryError as exc:
                out.append(
                    lib_issue(
                        "kicad.lib.missing-3d-model",
                        f"3D model of {fp.lib_id}: {exc.issue.message}",
                        where=fp.lib_id,
                    )
                )
                continue
            path = Path(expanded)
            if not path.is_absolute() and self.config.project_dir is not None:
                path = self.config.project_dir / path
            if not path.is_file():
                out.append(
                    lib_issue(
                        "kicad.lib.missing-3d-model",
                        f"3D model {path} of {fp.lib_id} not found",
                        where=fp.lib_id,
                    )
                )
        return tuple(out)


_BARE = re.compile(r'^[^\s()"]+$')


def _atom(value: str, *, quoted: bool) -> str:
    if quoted or not _BARE.match(value):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return value


def write_lib_table(table: LibTable, *, target: int = versions.DEFAULT_TARGET) -> str:
    """A project library table in the syntax of KiCad ``target`` (libraries.md, "Writing tables").

    Target 10 writes ``(version 7)`` and quotes every atom; target 9 writes no version and bare atoms,
    quoting only atoms that cannot be bare. Tab indentation and a final newline.
    """
    if target not in versions.TARGET_MAJORS:
        raise ValueError(f"unsupported target KiCad {target}; supported targets: {versions.TARGET_MAJORS}")
    root = next(name for name, kind in TABLE_ROOTS.items() if kind == table.kind)
    quoted = target >= 10
    lines = [f"({root}"]
    if quoted:
        lines.append("\t(version 7)")
    for row in table.rows:
        fields = " ".join(
            f"({key} {_atom(value, quoted=quoted)})"
            for key, value in zip(
                _ROW_FIELDS, (row.nickname, row.type, row.uri, row.options, row.descr), strict=True
            )
        )
        flags = (" (disabled)" if row.disabled else "") + (" (hidden)" if row.hidden else "")
        lines.append(f"\t(lib {fields}{flags})")
    return "\n".join(lines) + "\n)\n"


__all__ = [
    "write_lib_table",
    "SUPPORTED_TYPES",
    "TABLE_FILES",
    "LibRow",
    "LibTable",
    "LibraryConfig",
    "LibraryError",
    "LibraryResolver",
    "LibrarySource",
    "Location",
    "RowOrigin",
    "SourceKind",
    "TableKind",
    "COMMON_FILE",
    "find_library_sources",
    "read_lib_table",
    "scan_library_folder",
    "split_lib_id",
]
