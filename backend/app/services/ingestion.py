"""
DataGuard AI — Dataset Ingestion Service

Handles file validation, safe storage, CSV/Excel parsing with pandas,
and metadata generation. No database dependency.

Responsibilities:
  validate_file()       — extension, MIME, size, emptiness checks
  save_uploaded_file()  — collision-safe storage in uploads directory
  parse_csv()           — encoding-aware CSV parsing
  parse_excel()         — sheet-aware Excel parsing
  inspect_dataframe()   — column-level metadata extraction
  generate_metadata()   — assemble full UploadResponse

Type model:
  Column "dtype" is presented as one of five semantic types:
    - 'int'    : integer columns, or whole-number floats, or phone-like IDs
    - 'float'  : decimal numeric columns
    - 'string' : text columns
    - 'date'   : date columns (real datetime dtype, or strings that parse as dates)
    - 'bool'   : boolean columns
  This mirrors the classification used by profiling_service so the upload
  page, dataset page, and profile page agree on the label shown to users.
"""

import io
import csv
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import chardet
import pandas as pd

from app.config import settings
from app.schemas.dataset import ColumnMetadata, UploadResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ALLOWED_EXTENSIONS = {"csv", "xlsx"}
MIME_ALLOW_LIST = {
    "text/csv",
    "text/plain",  # some systems report CSV as text/plain
    "application/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/octet-stream",  # fallback for some browsers
}
SAMPLE_ROW_COUNT = 5
SAMPLE_VALUE_COUNT = 5
SENSITIVE_PATTERNS = [
    re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.IGNORECASE),
    re.compile(r"(\+?\d{1,3}[\s\-]?)?\(?\d{2,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{3,4}"),
    re.compile(r"\b\d{3}[\-\s]?\d{2}[\-\s]?\d{4}\b"),  # SSN-like
]

# Characters stripped from phone-number-like strings before digit check
_PHONE_STRIP_CHARS = str.maketrans("", "", "+-(). ")


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class IngestionError(Exception):
    """Base exception for ingestion errors."""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


# ---------------------------------------------------------------------------
# Semantic type detection
# ---------------------------------------------------------------------------
def _is_whole_number_column(series: pd.Series) -> bool:
    """
    Return True if a numeric column contains only whole numbers.
    Used to distinguish true integers that pandas promoted to float64
    because of missing values.
    """
    non_null = series.dropna()
    if len(non_null) == 0:
        return False

    try:
        coerced = pd.to_numeric(non_null, errors="coerce").dropna()
    except Exception:
        return False

    if len(coerced) == 0:
        return False

    try:
        return bool((coerced == coerced.astype("int64")).all())
    except Exception:
        # int64 overflow (values too large) → treat as float
        return False


def _looks_like_phone_identifier(series: pd.Series, threshold: float = 0.9) -> bool:
    """
    Return True if a string column looks like phone numbers:
      - After stripping + - ( ) . and spaces, ≥90% of samples are all digits.
      - Average digit count is between 7 and 15 (plausible phone range).
      - The column is highly unique (≥90% distinct values).
    """
    non_null = series.dropna().astype(str)
    if len(non_null) == 0:
        return False

    sample = non_null.head(50)
    stripped = sample.str.translate(_PHONE_STRIP_CHARS)
    all_digits = stripped.str.fullmatch(r"\d+")
    if all_digits.mean() < threshold:
        return False

    lengths = stripped[all_digits].str.len()
    if len(lengths) == 0:
        return False
    avg_len = lengths.mean()
    if not (7 <= avg_len <= 15):
        return False

    uniqueness = non_null.nunique() / len(non_null)
    return uniqueness >= 0.9


def _semantic_type(series: pd.Series) -> str:
    """
    Compute a user-facing semantic type for a column.

    Returns one of: 'int', 'float', 'string', 'date', 'bool'.

    Mirrors the type logic in profiling_service so the upload page and
    profile page agree on the label.
    """
    # 1. Boolean
    if pd.api.types.is_bool_dtype(series):
        return "bool"

    # 2. Integer (pandas already int)
    if pd.api.types.is_integer_dtype(series):
        return "int"

    # 3. Float — may be a whole-number column promoted due to nulls
    if pd.api.types.is_numeric_dtype(series):
        if _is_whole_number_column(series):
            return "int"
        return "float"

    # 4. Real datetime dtype
    if pd.api.types.is_datetime64_any_dtype(series):
        return "date"

    # 5. String column — check for phone identifier, then dates
    non_null = series.dropna()
    if len(non_null) == 0:
        return "string"

    # 5a. Phone-like identifier → int
    if _looks_like_phone_identifier(series):
        return "int"

    # 5b. Date detection
    sample = non_null.head(30).astype(str).tolist()
    try:
        parsed = pd.to_datetime(pd.Series(sample), errors="coerce")
        if parsed.notna().mean() >= 0.9:
            return "date"
    except Exception:
        pass

    return "string"


# ---------------------------------------------------------------------------
# File Validation
# ---------------------------------------------------------------------------
def validate_file(
    filename: str,
    content_type: str | None,
    file_size: int,
) -> str:
    """
    Validate uploaded file before processing.

    Returns the normalised file extension.
    Raises IngestionError on validation failure.
    """
    if not filename:
        raise IngestionError("No filename provided.")

    # Extension check
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise IngestionError(
            f"Unsupported file type '.{ext}'. "
            f"Accepted formats: {', '.join('.' + e for e in sorted(ALLOWED_EXTENSIONS))}."
        )

    # MIME type check (advisory — browsers are inconsistent)
    if content_type and content_type not in MIME_ALLOW_LIST:
        logger.warning(
            f"Unexpected MIME type '{content_type}' for file '{filename}'. "
            "Proceeding based on extension."
        )

    # Size checks
    if file_size == 0:
        raise IngestionError("The uploaded file is empty (0 bytes).")

    max_bytes = settings.max_upload_size_bytes
    if file_size > max_bytes:
        raise IngestionError(
            f"File size ({_format_bytes(file_size)}) exceeds the maximum "
            f"allowed size ({_format_bytes(max_bytes)})."
        )

    return ext


# ---------------------------------------------------------------------------
# Safe File Storage
# ---------------------------------------------------------------------------
def save_uploaded_file(file_content: bytes, original_filename: str, ext: str) -> Path:
    """
    Save uploaded file with a collision-safe unique name.

    Prevents path traversal, filename collisions, and partial writes.
    Returns the Path to the saved file.
    """
    # Generate a safe unique filename
    safe_name = f"{uuid.uuid4().hex}_{_sanitize_filename(original_filename)}"
    if not safe_name.endswith(f".{ext}"):
        safe_name = f"{safe_name}.{ext}"

    upload_dir = settings.upload_path
    dest = upload_dir / safe_name

    # Ensure the resolved path is inside the upload directory (prevent traversal)
    try:
        dest.resolve().relative_to(upload_dir.resolve())
    except ValueError:
        raise IngestionError("Invalid filename — path traversal detected.", status_code=400)

    # Write atomically via temp file to avoid partial uploads
    temp_dest = dest.with_suffix(dest.suffix + ".tmp")
    try:
        temp_dest.write_bytes(file_content)
        temp_dest.rename(dest)
        logger.info(f"File saved: {dest.name} ({_format_bytes(len(file_content))})")
    except Exception as e:
        # Cleanup on failure
        temp_dest.unlink(missing_ok=True)
        dest.unlink(missing_ok=True)
        logger.error(f"Failed to save file: {e}")
        raise IngestionError("Failed to save the uploaded file.", status_code=500)

    return dest


# ---------------------------------------------------------------------------
# CSV Parsing
# ---------------------------------------------------------------------------
def parse_csv(file_content: bytes) -> tuple[pd.DataFrame, str | None, str | None]:
    """
    Parse CSV content with encoding detection.

    Returns (DataFrame, detected_encoding, detected_delimiter).
    Raises IngestionError if the CSV cannot be parsed.
    """
    # Detect encoding
    detection = chardet.detect(file_content[:10000])
    encoding = detection.get("encoding", "utf-8") or "utf-8"
    logger.info(f"CSV encoding detected: {encoding} (confidence: {detection.get('confidence', 'N/A')})")

    # Decode text
    try:
        text = file_content.decode(encoding)
    except (UnicodeDecodeError, LookupError):
        # Fallback to utf-8, then latin-1
        for fallback in ("utf-8", "latin-1"):
            try:
                text = file_content.decode(fallback)
                encoding = fallback
                logger.warning(f"Encoding fallback to {fallback}")
                break
            except UnicodeDecodeError:
                continue
        else:
            raise IngestionError("Unable to decode the CSV file. Unsupported encoding.")

    # Detect delimiter
    delimiter = None
    try:
        sample = text[:8192]
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample)
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","  # default

    # Parse with pandas
    try:
        df = pd.read_csv(
            io.StringIO(text),
            sep=delimiter,
            on_bad_lines="warn",
            engine="python",
        )
    except pd.errors.EmptyDataError:
        raise IngestionError("The CSV file contains no data (empty or headers-only).")
    except pd.errors.ParserError as e:
        raise IngestionError(f"Malformed CSV file: {str(e)[:200]}")
    except Exception as e:
        raise IngestionError(f"Failed to parse CSV: {str(e)[:200]}")

    _validate_dataframe(df)
    return df, encoding, delimiter


# ---------------------------------------------------------------------------
# Excel Parsing
# ---------------------------------------------------------------------------
def parse_excel(file_content: bytes) -> tuple[pd.DataFrame, str]:
    """
    Parse Excel (.xlsx) content.

    Returns (DataFrame, sheet_name).
    Raises IngestionError if the Excel file cannot be parsed.
    """
    try:
        xls = pd.ExcelFile(io.BytesIO(file_content), engine="openpyxl")
    except Exception as e:
        raise IngestionError(f"Cannot read Excel file: {str(e)[:200]}")

    sheet_names = xls.sheet_names
    if not sheet_names:
        raise IngestionError("The Excel file contains no readable sheets.")

    # Use the first sheet
    sheet_name = sheet_names[0]
    logger.info(f"Excel sheets found: {sheet_names}. Using: '{sheet_name}'")

    try:
        df = pd.read_excel(xls, sheet_name=sheet_name, engine="openpyxl")
    except Exception as e:
        raise IngestionError(f"Failed to parse sheet '{sheet_name}': {str(e)[:200]}")

    _validate_dataframe(df)
    return df, sheet_name


# ---------------------------------------------------------------------------
# DataFrame Validation
# ---------------------------------------------------------------------------
def _validate_dataframe(df: pd.DataFrame) -> None:
    """Validate that the parsed DataFrame is usable."""
    if df.shape[0] == 0:
        raise IngestionError("The dataset contains zero rows after parsing.")
    if df.shape[1] == 0:
        raise IngestionError("The dataset contains zero columns after parsing.")


# ---------------------------------------------------------------------------
# DataFrame Inspection
# ---------------------------------------------------------------------------
def inspect_dataframe(df: pd.DataFrame) -> list[ColumnMetadata]:
    """
    Extract column-level metadata from a DataFrame.

    The `dtype` field now holds a semantic type — one of:
      'int', 'float', 'string', 'date', 'bool'
    This is consistent with the labels used on the profile page.
    """
    total_rows = len(df)
    columns_meta = []

    for col in df.columns:
        series = df[col]
        missing = int(series.isna().sum())
        non_null = series.dropna()
        unique = int(non_null.nunique())

        missing_pct = round((missing / total_rows * 100) if total_rows > 0 else 0, 2)
        unique_pct = round((unique / total_rows * 100) if total_rows > 0 else 0, 2)

        sample_vals = _get_safe_samples(non_null, SAMPLE_VALUE_COUNT)

        columns_meta.append(
            ColumnMetadata(
                name=str(col),
                dtype=_semantic_type(series),   # ← semantic type, not pandas dtype
                nullable=missing > 0,
                missing_count=missing,
                missing_percentage=missing_pct,
                unique_count=unique,
                unique_percentage=unique_pct,
                sample_values=sample_vals,
            )
        )

    return columns_meta


# ---------------------------------------------------------------------------
# Sample Row Generation
# ---------------------------------------------------------------------------
def generate_sample_rows(df: pd.DataFrame, n: int = SAMPLE_ROW_COUNT) -> list[dict]:
    """
    Return the first N rows as a list of dicts with values converted to
    JSON-safe types. Sensitive-looking cell values are masked.
    """
    sample_df = df.head(n).copy()

    # Convert to JSON-safe types
    for col in sample_df.columns:
        sample_df[col] = sample_df[col].apply(_to_json_safe)

    rows = sample_df.to_dict(orient="records")

    # Mask sensitive values in sample rows
    for row in rows:
        for key, value in row.items():
            if isinstance(value, str) and _looks_sensitive(value):
                row[key] = "***MASKED***"

    return rows


# ---------------------------------------------------------------------------
# Full Metadata Generation
# ---------------------------------------------------------------------------
def generate_metadata(
    df: pd.DataFrame,
    original_filename: str,
    stored_filename: str,
    file_type: str,
    file_size: int,
    encoding: str | None = None,
    delimiter: str | None = None,
    sheet_name: str | None = None,
) -> UploadResponse:
    """
    Assemble the complete upload response metadata.

    This function is the single output point for the ingestion pipeline.
    Phase 3 will persist the data returned here.
    """
    columns_meta = inspect_dataframe(df)
    sample_rows = generate_sample_rows(df)
    duplicate_count = int(df.duplicated().sum())

    # Build a column-name → semantic-type map (kept in the persisted metadata)
    column_semantic_types = {str(col): _semantic_type(df[col]) for col in df.columns}

    return UploadResponse(
        original_filename=original_filename,
        stored_filename=stored_filename,
        file_type=file_type,
        file_size_bytes=file_size,
        file_size_display=_format_bytes(file_size),
        encoding=encoding,
        delimiter=delimiter,
        sheet_name=sheet_name,
        row_count=len(df),
        column_count=len(df.columns),
        duplicate_row_count=duplicate_count,
        columns=columns_meta,
        sample_rows=sample_rows,
        uploaded_at=datetime.now(timezone.utc),
        column_names=[str(c) for c in df.columns],
        column_dtypes=column_semantic_types,   # ← semantic types, not pandas dtypes
    )


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------
def _format_bytes(size: int) -> str:
    """Convert byte count to human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _sanitize_filename(filename: str) -> str:
    """Remove unsafe characters from a filename."""
    name = Path(filename).stem
    # Keep only alphanumeric, underscore, hyphen, dot
    name = re.sub(r"[^\w\-.]", "_", name)
    # Truncate to reasonable length
    return name[:100]


def _looks_sensitive(value: str) -> bool:
    """Quick heuristic check if a string looks like PII."""
    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(value):
            return True
    return False


def _get_safe_samples(series: pd.Series, n: int) -> list:
    """Get sample values from a series, masking sensitive-looking strings."""
    if len(series) == 0:
        return []

    samples = series.head(n).tolist()
    safe_samples = []
    for val in samples:
        val = _to_json_safe(val)
        if isinstance(val, str) and _looks_sensitive(val):
            safe_samples.append("***MASKED***")
        else:
            safe_samples.append(val)
    return safe_samples


def _to_json_safe(val):
    """Convert a value to a JSON-serializable type."""
    if pd.isna(val):
        return None
    if isinstance(val, (pd.Timestamp, datetime)):
        return val.isoformat()
    if hasattr(val, "item"):  # numpy scalar
        return val.item()
    return val