# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Where a 3D model file is found (capability kicad-library-resolution, "3D model location" and "Missing
3D models are warnings"; change c0116). Hermetic: the install is a fake folder and the cache holds a
stamp written by the test."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from _libs import make_install
from _models import BOX, BOX_REL, MODELS, official, resolver

from fenolite.backends.kicad import libcache
from fenolite.backends.kicad.libs import ModelLocation
from fenolite.model.library import FootprintDef

SHA = hashlib.sha256(BOX.read_bytes()).hexdigest()


def _copy(folder: Path, rel: str = BOX_REL) -> Path:
    target = folder / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(BOX, target)
    return target


def test_vendored_copy_wins(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    copy = _copy(project / "3dmodels")
    found = resolver(tmp_path, project_dir=project, env={"KICAD10_3DMODEL_DIR": str(MODELS)})
    assert found.locate_model(official()) == ModelLocation(official(), BOX_REL, copy, "project")


def test_environment_before_the_install(tmp_path: Path) -> None:
    install = make_install(tmp_path / "install")
    in_install = _copy(install / "3dmodels")
    path = official(major=9)
    first = resolver(tmp_path, env={"KICAD9_3DMODEL_DIR": str(MODELS)}, install_dir=install)
    assert first.locate_model(path) == ModelLocation(path, BOX_REL, BOX, "env")
    second = resolver(tmp_path, install_dir=install)
    assert second.locate_model(path) == ModelLocation(path, BOX_REL, in_install, "install")
    # the install serves every N, as kicad-cli 10.0.6 reads KICAD9_ and KICAD10_ paths there
    assert second.locate_model(official(major=10)) == ModelLocation(
        official(), BOX_REL, in_install, "install"
    )


def test_only_the_variable_of_the_named_major_counts(tmp_path: Path) -> None:
    found = resolver(tmp_path, env={"KICAD10_3DMODEL_DIR": str(MODELS)})
    assert found.locate_model(official(major=9)) is None
    assert found.locate_model(official(major=10)) is not None


def test_kicad_configuration_is_read_only_on_request(tmp_path: Path) -> None:
    home = tmp_path / "kicad-config"
    (home / "9.0").mkdir(parents=True)
    common = {"environment": {"vars": {"KICAD9_3DMODEL_DIR": str(MODELS)}}}
    (home / "9.0" / "kicad_common.json").write_text(json.dumps(common), encoding="utf-8")
    path = official(major=9)
    assert resolver(tmp_path, config_home=home).locate_model(path) is None
    found = resolver(tmp_path, config_home=home, read_common=True, target_major=10).locate_model(path)
    assert found == ModelLocation(path, BOX_REL, BOX, "kicad-config")
    # a configuration file that cannot be read gives no source and no exception
    (home / "9.0" / "kicad_common.json").write_text("{not json", encoding="utf-8")
    assert resolver(tmp_path, config_home=home, read_common=True).locate_model(path) is None


def test_stale_cache_entry_is_not_used(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    folder = cache / "10.0.6" / libcache.MODEL_REPO
    copy = _copy(folder)
    (folder / libcache.MODEL_STAMP).write_text(json.dumps({BOX_REL: "0" * 64}), encoding="utf-8")
    assert resolver(tmp_path, cache_dir=cache).locate_model(official()) is None
    libcache.write_model_stamp(folder, {BOX_REL: SHA})
    found = resolver(tmp_path, cache_dir=cache).locate_model(official())
    assert found == ModelLocation(official(), BOX_REL, copy, "cache")
    # the cache of tag 10.0.6 serves major 10 only
    assert resolver(tmp_path, cache_dir=cache).locate_model(official(major=9)) is None
    assert not (folder / (libcache.MODEL_STAMP + ".part")).exists()


def test_not_found(tmp_path: Path) -> None:
    found = resolver(tmp_path, project_dir=tmp_path)
    assert found.locate_model(official()) is None
    assert found.locate_model("${NO_SUCH_VARIABLE}/x.step") is None
    assert found.locate_model("${KICAD10_3DMODEL_DIR}/../escape.step") is None
    assert found.locate_model("") is None


def test_project_relative_model(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    copy = _copy(project, "models/box.step")
    found = resolver(tmp_path, project_dir=project)
    path = "${KIPRJMOD}/models/box.step"
    assert found.locate_model(path) == ModelLocation(path, "models/box.step", copy, "project")
    assert found.locate_model("${KIPRJMOD}/models/absent.step") is None
    assert found.locate_model("${KIPRJMOD}/../outside.step") is None
    assert resolver(tmp_path).locate_model(path) is None  # no project folder is known


def test_other_forms_are_read_in_place(tmp_path: Path) -> None:
    found = resolver(tmp_path, env={"MY_MODELS": str(MODELS)})
    assert found.locate_model(str(BOX)) == ModelLocation(str(BOX), None, BOX, "in-place")
    path = f"${{MY_MODELS}}/{BOX_REL}"
    assert found.locate_model(path) == ModelLocation(path, None, BOX, "in-place")
    assert found.locate_model(str(tmp_path / "absent.step")) is None


def test_locating_defines_no_path_variable(tmp_path: Path) -> None:
    """ "Library sources" is unchanged: a cache still defines no ``KICAD<M>_3DMODEL_DIR``."""
    cache = tmp_path / "cache"
    folder = cache / "10.0.6" / libcache.MODEL_REPO
    _copy(folder)
    libcache.write_model_stamp(folder, {BOX_REL: SHA})
    found = resolver(tmp_path, cache_dir=cache)
    assert found.locate_model(official()) is not None
    assert "KICAD10_3DMODEL_DIR" not in found.variables()


# --- missing_models -----------------------------------------------------------------------------------


def _footprint(path: str) -> FootprintDef:
    return FootprintDef(id="fp-box", name="Box", library="Fenolite", models=(path,))


def test_missing_models_uses_the_same_sources(tmp_path: Path) -> None:
    empty = tmp_path / "models"
    empty.mkdir()
    absent = resolver(tmp_path, env={"KICAD10_3DMODEL_DIR": str(empty)})
    (warning,) = absent.missing_models(_footprint(official()))
    assert (warning.code, warning.severity) == ("kicad.lib.missing-3d-model", "warning")
    assert "not found" in warning.message and str(tmp_path) not in warning.message

    (unset,) = resolver(tmp_path).missing_models(_footprint(official()))
    assert "KICAD10_3DMODEL_DIR" in unset.message and "has no value" in unset.message

    project = tmp_path / "proj"
    _copy(project / "3dmodels")
    assert resolver(tmp_path, project_dir=project).missing_models(_footprint(official())) == ()
