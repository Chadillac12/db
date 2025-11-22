import sqlite3
from pathlib import Path

import pandas as pd

from build_requirements_db import (
    _apply_inference_to_record,
    build_default_doc_schema,
    create_sqlite_db,
    export_anythingllm_markdown,
    export_rag_text,
    normalize_req_id,
    normalize_srs,
    parse_id_list,
)


def test_normalize_req_id_padding_and_suffix():
    assert normalize_req_id("SSG-34") == "SSG-00034"
    assert normalize_req_id("FCSS-12A") == "FCSS-00012A"
    assert normalize_req_id("") == ""


def test_parse_id_list_deduplicates_and_normalizes():
    ids = parse_id_list("ssg-1; SSG-001; fcss-10a, FCSS-10A")
    assert ids == ["SSG-00001", "FCSS-00010A"]


def test_normalize_srs_merges_duplicates():
    data = [
        {
            "SRS Section": "3.2",
            "Req't No": "1a",
            "Requirement Text": "The system shall foo",
            "Traceability Doc Reqd #": "DOC-1",
            "Trace Source": "CSRD",
            "CSRD/SSG Requirement Text": "Foo requirement",
        },
        {
            "SRS Section": "3.2",
            "Req't No": "1a",
            "Requirement Text": "The system shall foo",
            "Traceability Doc Reqd #": "DOC-2",
            "Trace Source": "SSG",
            "CSRD/SSG Requirement Text": "Foo requirement",
        },
    ]
    df = pd.DataFrame(data)
    schema = build_default_doc_schema()
    spec = schema.get("SRS")
    normalized = normalize_srs(df, doc_name="SRS", doc_type="SRS", level="Software_Low", spec=spec)

    assert len(normalized) == 1
    row = normalized.iloc[0]
    assert row["Req_ID"] == "SRS-3.2-1a"
    assert row["Parent_Req_IDs"] == "DOC-00001, DOC-00002"
    assert "CSRD/SSG Requirement Text" in row["Combined_Text"]


def test_inference_from_req_id_populates_fields():
    schema = build_default_doc_schema()
    spec = schema.get("SRS")
    record = {
        "Req_ID": "SRS-3.2-1a",
        "SRS_Section": "",
        "SRS_Local_Req_No": "",
    }

    _apply_inference_to_record(record, spec, {"title": "", "number": "", "type": ""}, record["Req_ID"])

    assert record["SRS_Section"] == "3.2"
    assert record["SRS_Local_Req_No"] == "1a"
    assert record["Section_Inferred"] is True


def test_inference_inherits_section_state():
    schema = build_default_doc_schema()
    spec = schema.get("FCSS")
    record = {
        "Req_ID": "FCSS-00001",
        "Object_Number": "",
        "Section_Title": "",
        "Section_Number": "",
        "Section_Type": "",
    }
    section_state = {"title": "Hydraulics", "number": "1.2", "type": "header"}

    _apply_inference_to_record(record, spec, section_state, record["Req_ID"])

    assert record["Object_Number"] == "1.2"
    assert record["Section_Title"] == "Hydraulics"
    assert record["Section_Inferred"] is True


def test_export_markdown_unique_names(tmp_path: Path):
    df = pd.DataFrame(
        [
            {"Req_ID": "REQ-1", "Doc_Name": "Doc", "Doc_Type": "", "Level": "", "Requirement_Text": "A", "Combined_Text": "A", "Parent_Req_IDs": "", "Child_Req_IDs": ""},
            {"Req_ID": "REQ-1", "Doc_Name": "Doc", "Doc_Type": "", "Level": "", "Requirement_Text": "B", "Combined_Text": "B", "Parent_Req_IDs": "", "Child_Req_IDs": ""},
        ]
    )

    export_anythingllm_markdown(df, tmp_path)
    files = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*.md"))
    assert len(files) == 2
    assert files[0] != files[1]


def test_export_rag_text_creates_plain_files(tmp_path: Path):
    df = pd.DataFrame(
        [
            {
                "Req_ID": "REQ-1",
                "Doc_Name": "Doc",
                "Doc_Type": "Type",
                "Level": "L1",
                "Requirement_Text": "The system shall foo",
                "Combined_Text": "Requirement ID: REQ-1\nThe system shall foo",
                "Parent_Req_IDs": "P-1",
                "Child_Req_IDs": "C-1",
                "Section_Number": "1.2",
                "Section_Title": "Hydraulics",
                "Section_Type": "header",
                "Schema_Version": "test",
            }
        ]
    )

    export_rag_text(df, tmp_path)

    files = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*.txt"))
    assert files == [Path("Doc/REQ-1.txt")]

    content = (tmp_path / files[0]).read_text()
    assert "Tag: Info" in content
    assert "Requirement ID: REQ-1" in content
    assert "Combined Text:" in content
    assert "The system shall foo" in content


def test_create_sqlite_db_builds_tables(tmp_path: Path):
    df = pd.DataFrame(
        [
            {
                "Req_ID": "DOC-00001",
                "Doc_Name": "Doc",
                "Doc_Type": "Type",
                "Level": "L1",
                "Requirement_Text": "Parent requirement",
                "Combined_Text": "Parent requirement",
                "Parent_Req_IDs": "",
                "Child_Req_IDs": "DOC-00002",
            },
            {
                "Req_ID": "DOC-00002",
                "Doc_Name": "Doc",
                "Doc_Type": "Type",
                "Level": "L1",
                "Requirement_Text": "Child requirement",
                "Combined_Text": "Child requirement",
                "Parent_Req_IDs": "DOC-00001",
                "Child_Req_IDs": "",
            },
        ]
    )

    db_path = tmp_path / "requirements.db"
    create_sqlite_db(df, db_path=db_path, force_overwrite=True)

    conn = sqlite3.connect(db_path)
    try:
        doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        req_count = conn.execute("SELECT COUNT(*) FROM requirements").fetchone()[0]
        trace_count = conn.execute("SELECT COUNT(*) FROM traces").fetchone()[0]
    finally:
        conn.close()

    assert doc_count == 1
    assert req_count == 2
    assert trace_count == 2
