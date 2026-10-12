"""Tests for ``scripts/run_bafu_local.py`` source metadata emission."""

import importlib.util
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from sentier_importers.sources.bafu import ecospold
from sentier_importers.sources.bafu.provenance import BAFU_PROVENANCE, BAFU_PROVENANCE_IRI

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "run_bafu_local.py"


@pytest.fixture(scope="module")
def run_bafu_local():
    spec = importlib.util.spec_from_file_location("run_bafu_local", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stage(folder: Path, sectors: list[str], sources=None, versions=None) -> None:
    n = len(sectors)
    folder.mkdir(parents=True)
    pq.write_table(
        pa.table(
            {
                "process_id": [f"p{i}" for i in range(n)],
                "sector": sectors,
                "source": sources or [ecospold.SOURCE_ID] * n,
                "source_version": versions or [ecospold.SOURCE_VERSION] * n,
            }
        ),
        folder / "processes.parquet",
    )
    pq.write_table(
        pa.table({"process_id": ["p0", "p0"], "amount": [1.0, 2.0]}),
        folder / "exchanges.parquet",
    )


def test_source_metadata_has_exactly_the_inventory_keys_in_order(tmp_path, run_bafu_local):
    # the sentier-inventory schema/metadata.schema.json contract (0.3.0), key for key
    folder = tmp_path / ecospold.SOURCE_FOLDER
    _stage(folder, ["electricity", "agriculture", "electricity"])
    meta = run_bafu_local.source_metadata(folder)
    assert list(meta) == [
        "source",
        "source_version",
        "title",
        "publisher",
        "license",
        "citation",
        "source_url",
        "provenance",
        "retrieved",
        "schema_version",
        "sectors",
        "row_counts",
    ]


def test_source_metadata_values(tmp_path, run_bafu_local):
    folder = tmp_path / ecospold.SOURCE_FOLDER
    _stage(folder, ["electricity", "agriculture", "electricity"])
    meta = run_bafu_local.source_metadata(folder)
    assert meta["source"] == "bafu-2026"
    assert meta["source_version"] == "v1"
    assert meta["title"] == BAFU_PROVENANCE["title"]
    assert meta["publisher"] == BAFU_PROVENANCE["publisher"]
    assert meta["license"] == ecospold.LICENSE_SUMMARY
    assert meta["citation"] == BAFU_PROVENANCE["citation"]
    assert meta["source_url"] is None
    assert meta["provenance"] == BAFU_PROVENANCE_IRI
    assert meta["retrieved"] is None
    assert meta["schema_version"] == "0.3.0"
    assert meta["sectors"] == ["agriculture", "electricity"]  # distinct, sorted
    assert meta["row_counts"] == {"processes.parquet": 3, "exchanges.parquet": 2}


def test_source_metadata_rejects_a_second_source_in_the_folder(tmp_path, run_bafu_local):
    # one folder = one release of one source; a stray row from elsewhere is a bug
    folder = tmp_path / ecospold.SOURCE_FOLDER
    _stage(folder, ["waste", "waste"], sources=["bafu-2026", "other-1"])
    with pytest.raises(ValueError, match="source"):
        run_bafu_local.source_metadata(folder)


def test_source_metadata_rejects_a_second_version_in_the_folder(tmp_path, run_bafu_local):
    folder = tmp_path / ecospold.SOURCE_FOLDER
    _stage(folder, ["waste", "waste"], versions=["v1", "v2"])
    with pytest.raises(ValueError, match="source_version"):
        run_bafu_local.source_metadata(folder)


def test_source_metadata_requires_the_processes_file(tmp_path, run_bafu_local):
    folder = tmp_path / ecospold.SOURCE_FOLDER
    folder.mkdir()
    with pytest.raises(FileNotFoundError):
        run_bafu_local.source_metadata(folder)
