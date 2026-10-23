"""Data Quality & Exception Management Framework."""
from __future__ import annotations
import re
import sqlite3
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable


# ---------- Severity + exception hierarchy ----------
class Severity(IntEnum):
    LOW = 1       # log and continue
    MEDIUM = 2    # quarantine the record
    HIGH = 3      # quarantine and alert
    CRITICAL = 4  # stop the pipeline


class DataQualityError(Exception):
    severity = Severity.MEDIUM

    def __init__(self, field_name: str, value: Any, message: str, row_id: Any = None):
        self.field_name, self.value, self.row_id = field_name, value, row_id
        super().__init__(f"[{self.severity.name}] row={row_id} field={field_name}: {message} (value={value!r})")


class MissingValueError(DataQualityError):
    severity = Severity.HIGH


class FormatError(DataQualityError):
    severity = Severity.MEDIUM


class RangeError(DataQualityError):
    severity = Severity.MEDIUM


class DuplicateRecordError(DataQualityError):
    severity = Severity.HIGH


class SchemaError(DataQualityError):
    severity = Severity.CRITICAL


# ---------- Configurable validation rules ----------
@dataclass
class Rule:
    field: str
    check: Callable[[Any], bool]
    error: type[DataQualityError]
    message: str


def required(f): return Rule(f, lambda v: v not in (None, ""), MissingValueError, "value is required")
def pattern(f, rx): return Rule(f, lambda v: v is None or re.fullmatch(rx, str(v)) is not None, FormatError, f"must match {rx}")
def in_range(f, lo, hi): return Rule(f, lambda v: v is None or lo <= v <= hi, RangeError, f"must be between {lo} and {hi}")


@dataclass
class Report:
    valid: list = field(default_factory=list)
    quarantined: list = field(default_factory=list)  # (record, [errors])
    log: list = field(default_factory=list)

    def summary(self):
        by_sev = {}
        for _, errs in self.quarantined:
            for e in errs:
                by_sev[e.severity.name] = by_sev.get(e.severity.name, 0) + 1
        return {"valid": len(self.valid), "quarantined": len(self.quarantined), "errors_by_severity": by_sev}


class Validator:
    def __init__(self, rules: list[Rule], id_field="id", unique_fields=(), halt_on=Severity.CRITICAL):
        self.rules, self.id_field, self.unique_fields, self.halt_on = rules, id_field, unique_fields, halt_on

    def run(self, records: list[dict]) -> Report:
        report, seen = Report(), {f: set() for f in self.unique_fields}
        for rec in records:
            rid, errors = rec.get(self.id_field), []
            for r in self.rules:
                v = rec.get(r.field)
                if not r.check(v):
                    errors.append(r.error(r.field, v, r.message, rid))
            for f in self.unique_fields:
                v = rec.get(f)
                if v in seen[f]:
                    errors.append(DuplicateRecordError(f, v, "duplicate value", rid))
                elif v is not None:
                    seen[f].add(v)
            self._handle(rec, errors, report)
        return report

    def _handle(self, rec, errors, report):
        if not errors:
            report.valid.append(rec); return
        worst = max(e.severity for e in errors)
        for e in errors:
            report.log.append(str(e))
        if worst >= self.halt_on:
            raise errors[0]  # critical -> stop pipeline
        if worst == Severity.LOW:
            report.valid.append(rec)  # log and continue
        else:
            report.quarantined.append((rec, errors))


# ---------- SQL-based checks ----------
def run_sql_checks(conn: sqlite3.Connection, path="queries.sql") -> dict:
    """queries.sql holds blocks like:  -- name: null_emails  <newline> SELECT ...;"""
    text, results = open(path).read(), {}
    for block in re.split(r"--\s*name:\s*", text)[1:]:
        name, _, sql = block.partition("\n")
        results[name.strip()] = conn.execute(sql.strip().rstrip(";")).fetchall()
    return results


if __name__ == "__main__":
    data = [
        {"id": 1, "email": "a@x.com", "age": 25},
        {"id": 2, "email": "bad-email", "age": 30},
        {"id": 3, "email": "", "age": 200},
        {"id": 4, "email": "a@x.com", "age": 40},
    ]
    v = Validator(
        rules=[required("email"), pattern("email", r"[^@\s]+@[^@\s]+\.[a-z]+"), in_range("age", 0, 120)],
        unique_fields=("email",),
    )
    rep = v.run(data)
    print(rep.summary())
    print(*rep.log, sep="\n")

    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE users(id INTEGER, email TEXT, age INTEGER)")
    conn.executemany("INSERT INTO users VALUES(:id,:email,:age)", data)
    print(run_sql_checks(conn))