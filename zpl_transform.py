"""Utilities for normalizing Data Matrix records embedded in ZPL."""

import re


DATA_MATRIX_PREFIX_ORDER = ("1J", "P", "Q", "V", "1T")

# A Zebra Data Matrix field starts with ^BX, places its value after ^FD, and
# finishes at ^FS.  Restricting the command portion to non-caret characters
# keeps the match inside the current ZPL command.
_DATA_MATRIX_FIELD = re.compile(
    r"(?P<command>\^BX[^^]*\^FD)(?P<data>.*?)(?P<end>\^FS)",
    re.IGNORECASE | re.DOTALL,
)
_RECORD_DELIMITER = re.compile(r"(\\?\*/)")
_MESSAGE_TRAILER = re.compile(r"(\\?\*<\\?\*[\r\n]*)$")


def _record_prefix(record: str) -> str | None:
    """Return a supported record prefix without altering the record."""
    # Check the two-character identifiers before the one-character ones.
    for prefix in ("1J", "1T", "P", "Q", "V"):
        if record.startswith(prefix):
            return prefix
    return None


def _rearrange_field_data(data: str) -> str:
    """Reorder one Data Matrix field while preserving payload text exactly."""
    parts = _RECORD_DELIMITER.split(data)
    if len(parts) < 3:
        return data

    # The ISO/IEC 15434 message trailer belongs to the envelope, not to the
    # record that happens to precede it. Keep it at the end of the field.
    trailer = ""
    trailer_match = _MESSAGE_TRAILER.search(parts[-1])
    if trailer_match:
        trailer = trailer_match.group(1)
        parts[-1] = parts[-1][: trailer_match.start()]

    record_indexes = list(range(2, len(parts), 2))
    records_by_prefix: dict[str, tuple[int, str]] = {}

    for index in record_indexes:
        prefix = _record_prefix(parts[index])
        if prefix is None:
            continue
        # Ambiguous/duplicate records are left untouched to avoid data loss.
        if prefix in records_by_prefix:
            return data
        records_by_prefix[prefix] = (index, parts[index])

    # Only rewrite complete messages matching the requested five-record
    # schema. Partial or unrelated Data Matrix values remain unchanged.
    if set(records_by_prefix) != set(DATA_MATRIX_PREFIX_ORDER):
        return data

    target_indexes = sorted(index for index, _ in records_by_prefix.values())
    ordered_records = [records_by_prefix[prefix][1] for prefix in DATA_MATRIX_PREFIX_ORDER]
    for index, record in zip(target_indexes, ordered_records):
        parts[index] = record

    parts[-1] += trailer
    return "".join(parts)


def rearrange_datamatrix_fields(zpl: str) -> str:
    """Reorder every matching ^BX field in ZPL to 1J, P, Q, V, 1T."""
    if not isinstance(zpl, str):
        return zpl

    def replace_field(match: re.Match[str]) -> str:
        return "".join(
            (
                match.group("command"),
                _rearrange_field_data(match.group("data")),
                match.group("end"),
            )
        )

    return _DATA_MATRIX_FIELD.sub(replace_field, zpl)
