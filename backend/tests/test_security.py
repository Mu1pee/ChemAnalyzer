"""Защита загрузки структур белков (SSRF, подмена идентификаторов)."""

import asyncio

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from app.api import structure as st  # noqa: E402


@pytest.mark.parametrize("value", ["P35354", "p35354", "Q9Y6K9", "A0A024R161", "P04637"])
def test_valid_uniprot(value):
    assert st.normalize_accession(value) == value.upper()


@pytest.mark.parametrize(
    "value", ["", "P3535", "P35354-2", "12345", "DROP TABLE", "../etc", "P35354/../x"]
)
def test_invalid_uniprot(value):
    with pytest.raises(st.StructureError) as err:
        st.normalize_accession(value)
    assert err.value.status == 400


@pytest.mark.parametrize(
    "url",
    [
        "http://alphafold.ebi.ac.uk/x",
        "https://evil.com/alphafold.ebi.ac.uk/x",
        "https://alphafold.ebi.ac.uk.evil.com/x",
        "https://alphafold.ebi.ac.uk@evil.com/x",
        "file:///etc/passwd",
        "https://127.0.0.1/x",
        None,
        "",
    ],
)
def test_foreign_urls_rejected(url):
    assert st.safe_file_url(url) is None


def test_https_alphafold_url_allowed():
    assert st.safe_file_url("https://alphafold.ebi.ac.uk/files/AF-P1-F1-model_v6.pdb")


def test_parse_prediction_ignores_foreign_pdb_url():
    entry = {"entryId": "AF-X-F1", "pdbUrl": "https://evil.com/a.pdb"}
    assert st.parse_prediction([entry], "P35354") is None


def test_chembl_id_validation():
    for bad in ["CHEMBL", "230", "CHEMBL1;DROP", "../x"]:
        with pytest.raises(st.StructureError):
            asyncio.run(st.resolve_target(bad))
