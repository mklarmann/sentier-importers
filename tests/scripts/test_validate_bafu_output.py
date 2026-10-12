"""Tests for the per-sector counts and metadata agreement in ``validate_bafu_output.py``."""

import importlib.util
from pathlib import Path

import pyarrow as pa
import pytest
from sentier_importers.sources.bafu import ecospold

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "validate_bafu_output.py"


@pytest.fixture(scope="module")
def validate_bafu_output():
    spec = importlib.util.spec_from_file_location("validate_bafu_output", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _processes(sectors):
    n = len(sectors)
    return pa.table(
        {
            "process_id": [f"p{i}" for i in range(n)],
            "sector": sectors,
            "source": [ecospold.SOURCE_ID] * n,
            "source_version": [ecospold.SOURCE_VERSION] * n,
        }
    )


def _metadata(**overrides):
    meta = {
        "source": ecospold.SOURCE_ID,
        "source_version": ecospold.SOURCE_VERSION,
        "sectors": ["energy", "waste"],
        "row_counts": {"processes.parquet": 3, "exchanges.parquet": 5},
    }
    meta.update(overrides)
    return meta


def test_sector_counts_come_from_the_column(validate_bafu_output):
    counts = validate_bafu_output.sector_counts(_processes(["waste", "energy", "waste"]))
    assert counts == {"energy": 1, "waste": 2}


def test_metadata_agrees_with_the_staged_tables(validate_bafu_output):
    proc = _processes(["waste", "energy", "waste"])
    assert validate_bafu_output.metadata_mismatches(_metadata(), proc, exchange_rows=5) == []


def test_metadata_mismatches_name_every_disagreeing_key(validate_bafu_output):
    proc = _processes(["waste", "energy", "waste"])
    meta = _metadata(
        source="other-1",
        source_version="v2",
        sectors=["energy"],
        row_counts={"processes.parquet": 4, "exchanges.parquet": 5},
    )
    mismatches = validate_bafu_output.metadata_mismatches(meta, proc, exchange_rows=5)
    assert len(mismatches) == 4
    assert any("source_version" in m for m in mismatches)
    assert any("sectors" in m for m in mismatches)
    assert any("processes.parquet" in m for m in mismatches)
