from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, MutableMapping, Sequence


def clean_header_name(name: str):
    """
    Clean noisy Excel headers by collapsing repeated words/phrases.

    Mirrors the logic used by the diff tool so browser/diff share the same
    normalization behavior.
    """
    if not name:
        return name

    tokens = str(name).strip().split()
    n_tokens = len(tokens)
    if n_tokens == 0:
        return name

    # Detect repeated phrases (e.g., "Name NAME" -> "Name").
    for chunk_size in range(1, n_tokens // 2 + 1):
        if n_tokens % chunk_size != 0:
            continue
        chunks = [tokens[i : i + chunk_size] for i in range(0, n_tokens, chunk_size)]
        first_norm = [x.lower() for x in chunks[0]]
        if all([x.lower() for x in c] == first_norm for c in chunks[1:]):
            return clean_header_name(" ".join(chunks[0]))

    cleaned: List[str] = []
    for token in tokens:
        if not cleaned or cleaned[-1].lower() != token.lower():
            cleaned.append(token)
    return " ".join(cleaned)


@dataclass(frozen=True)
class TableSchema:
    """Canonical schema definition for a logical ICD table."""

    name: str
    columns: Mapping[str, str]  # canonical -> raw column name
    keys: Sequence[str]
    fill_down: Sequence[str] = ()


SYSTEM_COLS: Mapping[str, str] = {
    "System_LOID": "System LOID LOID",
    "System_Name": "System Name NAME",
    "System_Bus": "System Bus LEFT or RIGHT",
}

PHYSPORT_COLS: Mapping[str, str] = {
    "PhysicalPort_LOID": "A629 Physical Port Occ LOID LOID",
    "System_LOID": "System LOID LOID",
    "PhysicalPort_Name": "A629 Physical Port Name NAME",
    "PhysicalPort_Occ_LOID": "A629 Physical Port Occ LOID LOID",
    "PhysicalPort_CID": "A629 Physical Port CID Channel ID",
    "PhysicalPort_Lane": "A629 Physical Port Lane Lane",
    "PhysicalPort_SG": "A629 Physical Port SG Sync Gap",
    "PhysicalPort_TG": "A629 Physical Port TG Terminal Gap",
    "PhysicalPort_TI": "A629 Physical Port TI Transmit Interval",
}

OUTPUTPORT_COLS: Mapping[str, str] = {
    "OutputPort_LOID": "A629 Output Port Occ LOID LOID",
    "PhysicalPort_LOID": "A629 Physical Port Occ LOID LOID",
    "OutputPort_Name": "A629 Output Port Name A629 Label",
    "OutputPort_Def_LOID": "A629 Output Port Def LOID LOID",
    "OutputPort_Occ_LOID": "A629 Output Port Occ LOID LOID",
    "OutputPort_Rate_ms": "A629 Output Port Rate (ms) Refresh Rate/TC Update Rate",
    "OutputPort_StrikeCnt": "A629 Output Port Strike Count Freshness Strike Count",
    "OutputPort_SSW": "A629 Output Port SSW A629 Label",
    "OutputPort_Label": "A629 Output Port Label A629 Label",
}

WORDSTRING_COLS: Mapping[str, str] = {
    "Wordstring_LOID": "A629 Wordstring LOID LOID",
    "OutputPort_LOID": "A629 Output Port Occ LOID LOID",
    "Wordstring_Name": "A629 Wordstring Wordstring Name NAME",
    "Wordstring_Type": "A629 Wordstring Wordstring Type SUB_TYPE_NAME",
    "Wordstring_Mnemonic": "A629 Wordstring Mnemonic Mnemonic",
    "Wordstring_TotalWords": "A629 Wordstring Total Words Word Count",
}

WORD_COLS: Mapping[str, str] = {
    "Wordstring_LOID": "A629 Wordstring LOID LOID",
    "Word_Seq_Num": "A629 Wordstring Word Seq Num A629 Word Number",
    "Word_Name": "A629 Wordstring Word Name NAME",
    "Word_Type": "A629 Wordstring Word Type SUB_TYPE_NAME",
    "Word_Bit_Type": "A629 Wordstring Bit Type Bit Type",
    "Word_Start_Bit": "A629 Wordstring Start Bit Local Start Bit",
    "Word_CalcEnd_Bit": "A629 Wordstring Calc'd End Bit Start Bit + Bit Length - 1",
    "Word_Bit_Length": "A629 Wordstring Bit Length Bit Length",
    "Word_PVB": "A629 Wordstring PVB PVB",
}

PARAMETER_COLS: Mapping[str, str] = {
    "Parameter_LOID": "Parameter Def LOID LOID",
    "OutputPort_LOID": "A629 Output Port Occ LOID LOID",
    "Parameter_Name": "Parameter Digital Output Parameter Name NAME",
    "Parameter_Def_LOID": "Parameter Def LOID LOID",
    "Parameter_UsgOcc_LOID": "Parameter Usg/Occ LOID LOID",
    "Parameter_UsgBase_GUID": "Parameter Usg Base GUID Base GUID",
    "Parameter_EU_Element": "Parameter EU Element Used",
    "Parameter_MinorModel": "Parameter Minor Model Model",
    "Parameter_DataType": "Parameter Data Type Bit Type/Data Format Type",
    "Parameter_DataSize": "Parameter Data Size Data Size",
    "Parameter_SignBit": "Parameter Sign Bit Sign Bit",
    "Parameter_NumSigBits": "Parameter Num Sig Bits Significant Bit",
    "Parameter_LSB_Res": "Parameter LSB Res LSB Resolution",
    "Parameter_FullScale_LwrBnd": "Parameter Full Scaled Range Lwr Bnd Full Scaled Rng - Lwr Bnd",
    "Parameter_FullScale_UprBnd": "Parameter Upr Bnd Full Scaled Rng - Upr Bnd",
    "Parameter_FuncRange_Min": "Parameter Functional Range Min Functional Range Mininum",
    "Parameter_FuncRange_Max": "Parameter Max Functional Range Maximum",
    "Parameter_Units": "Parameter Units Functional Range Units",
    "Parameter_PosSense": "Parameter Positive Sense Positive Sense",
    "Parameter_DigitalState": "Parameter Digital State Digital State",
    "Parameter_Accuracy_LwrBnd": "Parameter Accuracy Lwr Bnd Accuracy - Lower Bound",
    "Parameter_Accuracy_UprBnd": "Parameter Upr Bnd Accuracy - Upper Bound",
    "Parameter_Mnemonic": "Parameter Mnemonic Mnemonic",
    "Parameter_DataDesc": "Parameter Data Description Data Description",
    "Parameter_TI_Min_ms": "Parameter TI Min (ms) Transmit Interval Minimum",
    "Parameter_CompInterval_ms": "Parameter Comp Interval (ms) Computation Interval",
    "Parameter_CCSInterface": "Parameter CCS Interface CCS Interface",
    "Parameter_Latency_ms": "Parameter Latency (ms) Latency",
    "Parameter_Description": "Parameter Description Description",
}

REPORT_COLS: Mapping[str, str] = {
    "Database_DateTime": "Report Timestamp Database Date/Time",
    "Col_59": "col_59",
    "Col_60": "col_60",
}


def _table_schema() -> Dict[str, TableSchema]:
    """Build immutable table schema map."""

    return {
        "system": TableSchema(
            "system",
            SYSTEM_COLS,
            keys=("System_LOID",),
            fill_down=("System_LOID", "System_Name", "System_Bus"),
        ),
        "physport": TableSchema(
            "physport",
            PHYSPORT_COLS,
            keys=("PhysicalPort_LOID",),
            fill_down=(
                "PhysicalPort_LOID",
                "System_LOID",
                "PhysicalPort_Name",
                "PhysicalPort_CID",
                "PhysicalPort_Lane",
                "PhysicalPort_SG",
                "PhysicalPort_TG",
                "PhysicalPort_TI",
            ),
        ),
        "outputport": TableSchema(
            "outputport",
            OUTPUTPORT_COLS,
            keys=("OutputPort_LOID",),
            fill_down=(
                "OutputPort_LOID",
                "PhysicalPort_LOID",
                "OutputPort_Name",
                "OutputPort_Def_LOID",
                "OutputPort_Occ_LOID",
                "OutputPort_Rate_ms",
                "OutputPort_StrikeCnt",
                "OutputPort_SSW",
                "OutputPort_Label",
            ),
        ),
        "wordstring": TableSchema(
            "wordstring",
            WORDSTRING_COLS,
            keys=("Wordstring_LOID",),
            fill_down=(
                "Wordstring_LOID",
                "OutputPort_LOID",
                "Wordstring_Name",
                "Wordstring_Type",
                "Wordstring_Mnemonic",
                "Wordstring_TotalWords",
            ),
        ),
        "word": TableSchema(
            "word",
            WORD_COLS,
            keys=("Wordstring_LOID", "Word_Seq_Num"),
            fill_down=(
                "Wordstring_LOID",
                "Word_Seq_Num",
                "Word_Name",
                "Word_Type",
                "Word_Bit_Type",
                "Word_Start_Bit",
                "Word_CalcEnd_Bit",
                "Word_Bit_Length",
                "Word_PVB",
            ),
        ),
        "parameter": TableSchema(
            "parameter",
            PARAMETER_COLS,
            keys=("Parameter_LOID",),
            fill_down=(
                "Parameter_LOID",
                "OutputPort_LOID",
                "Parameter_Name",
                "Parameter_Def_LOID",
                "Parameter_UsgOcc_LOID",
                "Parameter_UsgBase_GUID",
                "Parameter_EU_Element",
                "Parameter_MinorModel",
                "Parameter_DataType",
                "Parameter_DataSize",
                "Parameter_SignBit",
                "Parameter_NumSigBits",
                "Parameter_LSB_Res",
                "Parameter_FullScale_LwrBnd",
                "Parameter_FullScale_UprBnd",
                "Parameter_FuncRange_Min",
                "Parameter_FuncRange_Max",
                "Parameter_Units",
                "Parameter_PosSense",
                "Parameter_DigitalState",
                "Parameter_Accuracy_LwrBnd",
                "Parameter_Accuracy_UprBnd",
                "Parameter_Mnemonic",
                "Parameter_DataDesc",
                "Parameter_TI_Min_ms",
                "Parameter_CompInterval_ms",
                "Parameter_CCSInterface",
                "Parameter_Latency_ms",
                "Parameter_Description",
            ),
        ),
        "report": TableSchema(
            "report",
            REPORT_COLS,
            keys=(),
            fill_down=(),
        ),
    }


TABLE_SCHEMAS: Dict[str, TableSchema] = _table_schema()
REQUIRED_TABLES: Sequence[str] = ("system", "physport", "outputport", "wordstring", "word", "parameter")
HIERARCHY_COLUMNS: Sequence[str] = ("System_LOID", "PhysicalPort_LOID", "OutputPort_LOID", "Wordstring_LOID")


def merge_column_mappings(
    overrides: Mapping[str, Mapping[str, str]] | None,
    base: Mapping[str, Mapping[str, str]] | None = None,
) -> Dict[str, Dict[str, str]]:
    """
    Merge overrides into the canonical table schemas.

    Overrides are canonical->raw per table. Missing entries fall back to
    defaults so callers only need to specify the deltas.
    """

    mapping: Dict[str, Dict[str, str]] = {k: dict(v) for k, v in (base or {}).items()}
    if not mapping:
        mapping = {name: dict(schema.columns) for name, schema in TABLE_SCHEMAS.items()}

    if overrides:
        for table, cols in overrides.items():
            target = mapping.setdefault(table, {})
            for k, v in cols.items():
                target[str(k)] = str(v)
    return mapping


def schema_required_raw_columns(
    mapping: Mapping[str, Mapping[str, str]] | None = None,
    required_tables: Iterable[str] | None = None,
) -> set[str]:
    """Return the set of raw column names required to normalize an ICD export."""

    tables = required_tables or REQUIRED_TABLES
    mapping = mapping or merge_column_mappings(None)
    required: set[str] = set()
    for table in tables:
        if table not in mapping:
            continue
        required.update(mapping[table].values())
    return required


def default_fill_down_canonical(required_tables: Iterable[str] | None = None) -> List[str]:
    """Canonical fill-down defaults derived from the table schemas."""

    tables = required_tables or REQUIRED_TABLES
    found: List[str] = []
    for table in tables:
        schema = TABLE_SCHEMAS.get(table)
        if not schema:
            continue
        for col in schema.fill_down:
            if col not in found:
                found.append(col)
    return found


def canonical_to_raw(fill_down: Iterable[str], mapping: Mapping[str, Mapping[str, str]]) -> List[str]:
    """Translate canonical column names to raw column names using the provided mapping."""

    raw: List[str] = []
    for col in fill_down:
        col_str = str(col)
        for table_map in mapping.values():
            if col_str in table_map:
                raw_name = table_map[col_str]
                if raw_name not in raw:
                    raw.append(raw_name)
                break
    return raw


DEFAULT_COLUMN_MAPS: Dict[str, Dict[str, str]] = merge_column_mappings(None)
DEFAULT_FILL_DOWN_CANONICAL: List[str] = default_fill_down_canonical()
