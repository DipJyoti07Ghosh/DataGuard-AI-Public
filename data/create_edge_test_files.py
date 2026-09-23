"""
Create edge-case test files for Phase 2 verification.
"""
import pandas as pd
from pathlib import Path

data_dir = Path(__file__).parent

# 1. Normal XLSX
df_clean = pd.read_csv(data_dir / "clean_sample.csv")
df_clean.to_excel(data_dir / "sample_excel.xlsx", sheet_name="CustomerData", index=False)
print("Created: sample_excel.xlsx")

# 2. Empty CSV
(data_dir / "empty.csv").write_bytes(b"")
print("Created: empty.csv")

# 3. Malformed CSV
(data_dir / "malformed.csv").write_text('col1,col2\n"unclosed quote,123\n456,789\n"another broken line', encoding="utf-8")
print("Created: malformed.csv")

# 4. Corrupted XLSX
(data_dir / "corrupted.xlsx").write_bytes(b"PK\x03\x04corrupted fake excel data header\x00\x00\xff\xff")
print("Created: corrupted.xlsx")

# 5. Unsupported file
(data_dir / "unsupported.json").write_text('{"key": "value", "type": "unsupported"}', encoding="utf-8")
print("Created: unsupported.json")

# 6. Special characters in column names
df_special = pd.DataFrame({
    "Order # / ID": [101, 102, 103],
    "Tax Rate (%)": [8.5, 7.0, 9.25],
    "Customer & Co.": ["Acme Corp", "Beta LLC", "Gamma Inc"],
    "Price ($ / USD)": [99.99, 149.50, 20.00],
    "Status [Active?]": [True, False, True]
})
df_special.to_csv(data_dir / "special_columns.csv", index=False, encoding="utf-8")
print("Created: special_columns.csv")
