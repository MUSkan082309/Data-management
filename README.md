# Data Quality & Exception Management Framework

Python framework to detect, classify and handle data quality issues.

- **Exception hierarchy:** `DataQualityError` -> `MissingValueError`, `FormatError`, `RangeError`, `DuplicateRecordError`, `SchemaError`, each with a `Severity` (LOW/MEDIUM/HIGH/CRITICAL).
- **Validation rules:** configurable `Rule` objects (`required`, `pattern`, `in_range`) plus uniqueness checks.
- **Handling:** LOW is logged, MEDIUM/HIGH records are quarantined, CRITICAL stops the pipeline.
- **SQL checks:** named queries in `queries.sql` run via `run_sql_checks`.

Run: `python dq_framework.py`