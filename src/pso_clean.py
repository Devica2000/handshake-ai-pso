"""Shared loading, cleaning and aggregation for the PSO funnel case study.

Both the EDA notebook and the dashboard build import this module, so the numbers
in the write-up and the numbers on the dashboard cannot drift apart.

The unit of analysis throughout is a *PSO instance*: one (tasker_id, project_id)
pair. A tasker can be onboarding onto several projects at once and sit at a
different funnel step in each, so the tasker is not the right grain.

`build_instance_records` is the one implementation of the funnel logic. It uses
only the standard library and streams the file in a single pass, which keeps the
dashboard build to tens of megabytes. `build_instances` is a thin pandas wrapper
over the same records for notebook use.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_FILE = "pso_funnel_events - pso_funnel_events.csv"

# The export is dated 2026-09-01; everything after this is right-censored.
EXTRACT_DATE = datetime(2026, 9, 1, tzinfo=timezone.utc)

# p90 of allocated -> pso_completed is ~7.8 days, so an instance needs roughly a
# week before its deep-funnel outcome is knowable.
MATURITY_DAYS = 7

# The ordered PSO funnel. Email steps are included because they are in the
# pipeline, but see EMAIL_TRACKING_STEPS below: they are not reliably observed.
FUNNEL_STEPS = [
    "pso_allocated",
    "email_sent",
    "email_delivered",
    "email_opened",
    "email_clicked",
    "pso_accepted",
    "confidentiality_agreement_signed",
    "assessment_started",
    "assessment_attempted",
    "assessment_passed",
    "contract_started",
    "contract_finished",
    "pso_completed",
    "first_task_claimed",
    "first_task_submitted",
]

# Open/click pixels undercount: some instances accept with no recorded open, and
# some accept in-app having never touched the email at all. Drops across these
# two steps are part measurement, part real, and we cannot separate them.
EMAIL_TRACKING_STEPS = ["email_opened", "email_clicked"]

LIKENESS_STEPS = ["likeness_agreement_signed", "likeness_agreement_declined"]

# The raw `device` column arrives with mixed casing and a mix of form factors and
# operating systems. Collapse to form factor, which is what the funnel cares about.
DEVICE_MAP = {
    "mobile": "mobile",
    "Mobile": "mobile",
    "iOS": "mobile",
    "Android": "mobile",
    "desktop": "desktop",
    "Desktop": "desktop",
    "web": "desktop",
    "tablet": "tablet",
    "iPad": "tablet",
}

# Attempt rate steps down sharply between a 30- and a 40-minute assessment
# rather than sloping, so bucket on that boundary.
LONG_ASSESSMENT_MINUTES = 40

EXPECTED_DUPLICATE_ROWS = 3_121
EXPECTED_EVENTS = 312_148
EXPECTED_INSTANCES = 53_935


def data_path(root: str | Path = ".") -> Path:
    return Path(root) / DATA_FILE


def _parse_ts(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _week_start(ts: datetime) -> str:
    """Monday of the ISO week containing ts, as YYYY-MM-DD."""
    return (ts - timedelta(days=ts.weekday())).date().isoformat()


def build_instance_records(path: str | Path | None = None) -> tuple[list[dict], dict]:
    """Stream the export and collapse it to one record per PSO instance.

    Returns (records, stats). Standard library only, one pass, no sorting: the
    event_ts strings are fixed-width ISO-8601 in UTC, so a lexicographic
    comparison is also a chronological one and nothing needs parsing until the
    very end.

    The pipeline emitted rows that are byte-identical to another row on all 14
    columns, duplicate event_id included. They are a replay artifact, not two
    real occurrences, so repeated event_ids are skipped.
    """
    path = Path(path) if path is not None else data_path()
    csv.field_size_limit(sys.maxsize)

    seen_ids: set[str] = set()
    instances: dict[tuple[str, str], dict] = {}
    duplicates = 0
    kept = 0
    unmapped_devices: set[str] = set()
    ts_min = ts_max = None

    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            eid = row["event_id"]
            if eid in seen_ids:
                duplicates += 1
                continue
            seen_ids.add(eid)
            kept += 1

            ts = row["event_ts"]
            if ts_min is None or ts < ts_min:
                ts_min = ts
            if ts_max is None or ts > ts_max:
                ts_max = ts

            key = (row["tasker_id"], row["project_id"])
            rec = instances.get(key)
            if rec is None:
                rec = instances[key] = {
                    "tasker_id": key[0],
                    "project_id": key[1],
                    "project_name": row["project_name"],
                    "country": row["country"],
                    "tasker_tenure": row["tasker_tenure"],
                    "prior_projects_completed": int(row["prior_projects_completed"]),
                    "concurrent_psos": int(row["concurrent_psos"]),
                    "assessment_est_minutes": int(row["assessment_est_minutes"]),
                    "likeness_variant": None,
                    "assessment_device": None,
                    "assessment_starts": 0,
                    "assessment_session_seconds": None,
                    "assessment_questions_answered": None,
                    "assessment_score": None,
                    "accept_source": None,
                    "likeness_placement": None,
                    "_device_ts": None,
                }
                for step in FUNNEL_STEPS:
                    rec["ts_" + step] = None
                for step in LIKENESS_STEPS:
                    rec["reached_" + step] = False

            if row["likeness_variant"]:
                rec["likeness_variant"] = row["likeness_variant"]

            name = row["event_name"]
            if name in LIKENESS_STEPS:
                rec["reached_" + name] = True
            else:
                col = "ts_" + name
                if col in rec and (rec[col] is None or ts < rec[col]):
                    rec[col] = ts

            if name == "assessment_started":
                rec["assessment_starts"] += 1
                raw_device = row["device"]
                if raw_device:
                    if raw_device not in DEVICE_MAP:
                        unmapped_devices.add(raw_device)
                    # Device is missing on some starts, so take it from the
                    # earliest start that actually recorded one.
                    if rec["_device_ts"] is None or ts < rec["_device_ts"]:
                        rec["_device_ts"] = ts
                        rec["assessment_device"] = DEVICE_MAP[raw_device]

            props = row["properties"]
            if props:
                p = json.loads(props)
                if name == "assessment_started":
                    # Several starts per instance are possible; keep the furthest progress.
                    for src, dst in (("session_seconds", "assessment_session_seconds"),
                                     ("questions_answered", "assessment_questions_answered")):
                        v = p.get(src)
                        if v is not None and (rec[dst] is None or v > rec[dst]):
                            rec[dst] = v
                elif name == "assessment_passed":
                    rec["assessment_score"] = p.get("score")
                elif name == "pso_accepted":
                    rec["accept_source"] = p.get("source")
                elif name == "likeness_agreement_signed":
                    rec["likeness_placement"] = p.get("placement")

    assert not unmapped_devices, f"unmapped device values: {unmapped_devices}"

    records = list(instances.values())
    for rec in records:
        rec.pop("_device_ts")
        for step in FUNNEL_STEPS:
            rec["reached_" + step] = rec["ts_" + step] is not None

        alloc = _parse_ts(rec["ts_pso_allocated"])
        rec["alloc_date"] = alloc.date().isoformat()
        rec["alloc_week"] = _week_start(alloc)
        rec["days_since_alloc"] = (EXTRACT_DATE - alloc).total_seconds() / 86400
        rec["mature"] = rec["days_since_alloc"] >= MATURITY_DAYS

        est = rec["assessment_est_minutes"]
        rec["long_assessment"] = est >= LONG_ASSESSMENT_MINUTES
        rec["assessment_length_bucket"] = (
            f"{LONG_ASSESSMENT_MINUTES}+ min" if rec["long_assessment"]
            else f"under {LONG_ASSESSMENT_MINUTES} min"
        )

    # Sorting by allocation keeps the dashboard's row order stable between builds.
    records.sort(key=lambda r: (r["ts_pso_allocated"], r["tasker_id"], r["project_id"]))

    stats = {
        "events_deduped": kept,
        "duplicate_rows_dropped": duplicates,
        "instances": len(records),
        "taskers": len({r["tasker_id"] for r in records}),
        "projects": len({r["project_id"] for r in records}),
        "ts_min": ts_min,
        "ts_max": ts_max,
    }
    return records, stats


def raw_quality_report(path: str | Path | None = None) -> dict:
    """One streaming pass over the raw file for the data-quality checks.

    Avoids holding a 312k-row DataFrame just to count duplicates and nulls.
    `duplicate_rows` counts rows byte-identical to one already seen; if that
    equals `duplicate_event_ids`, every repeated id is a true replay and
    de-duplicating on event_id alone is safe.
    """
    path = Path(path) if path is not None else data_path()
    csv.field_size_limit(sys.maxsize)

    seen_rows: set[tuple] = set()
    seen_ids: set[str] = set()
    duplicate_rows = duplicate_event_ids = total = 0
    device_counts: dict[str, int] = defaultdict(int)
    null_counts: dict[str, int] = defaultdict(int)
    event_counts: dict[str, int] = defaultdict(int)

    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fields = list(reader.fieldnames or [])
        for row in reader:
            total += 1
            key = tuple(row[f] for f in fields)
            if key in seen_rows:
                duplicate_rows += 1
            else:
                seen_rows.add(key)
            if row["event_id"] in seen_ids:
                duplicate_event_ids += 1
            else:
                seen_ids.add(row["event_id"])
            device_counts[row["device"] or "(null)"] += 1
            event_counts[row["event_name"]] += 1
            for f in fields:
                if row[f] == "":
                    null_counts[f] += 1

    return {
        "total_rows": total,
        "duplicate_rows": duplicate_rows,
        "duplicate_event_ids": duplicate_event_ids,
        "every_duplicate_id_is_an_identical_row": duplicate_rows == duplicate_event_ids,
        "device_counts": dict(sorted(device_counts.items(), key=lambda kv: -kv[1])),
        "null_counts": dict(sorted(null_counts.items(), key=lambda kv: -kv[1])),
        "event_counts": dict(sorted(event_counts.items(), key=lambda kv: -kv[1])),
        "fields": fields,
    }


def validate_records(records: list[dict], stats: dict) -> dict:
    """Assert the invariants established during exploration.

    If one of these trips, either the input data changed or the cleaning is
    wrong; either way the downstream numbers should not be trusted.
    """
    assert stats["duplicate_rows_dropped"] == EXPECTED_DUPLICATE_ROWS, (
        f"expected {EXPECTED_DUPLICATE_ROWS:,} duplicate rows, "
        f"dropped {stats['duplicate_rows_dropped']:,}"
    )
    assert stats["events_deduped"] == EXPECTED_EVENTS, (
        f"expected {EXPECTED_EVENTS:,} deduped events, got {stats['events_deduped']:,}"
    )
    assert len(records) == EXPECTED_INSTANCES, (
        f"expected {EXPECTED_INSTANCES:,} instances, got {len(records):,}"
    )
    assert stats["ts_min"] >= "2026-06-01", f"event before the stated window: {stats['ts_min']}"
    assert stats["ts_max"] < "2026-09-01", f"event after the extract date: {stats['ts_max']}"
    assert all(r["reached_pso_allocated"] for r in records), "instance with no allocation event"

    # No funnel step may be timestamped before the step preceding it.
    violations: dict[str, int] = {}
    for earlier, later in zip(FUNNEL_STEPS, FUNNEL_STEPS[1:]):
        bad = sum(
            1 for r in records
            if r["ts_" + later] is not None and r["ts_" + earlier] is not None
            and r["ts_" + later] < r["ts_" + earlier]
        )
        if bad:
            violations[f"{later} before {earlier}"] = bad
    assert not violations, f"out-of-order transitions: {violations}"

    return {**{k: v for k, v in stats.items() if not k.startswith("ts_")},
            "out_of_order_transitions": 0}


def funnel_counts(records: list[dict], steps: list[str] | None = None) -> dict[str, int]:
    """Instances that ever reached each step."""
    steps = steps or FUNNEL_STEPS
    return {s: sum(1 for r in records if r["reached_" + s]) for s in steps}


# --------------------------------------------------------------------------
# pandas conveniences — used by the notebook. The dashboard build does not
# import pandas at all.
# --------------------------------------------------------------------------

def build_instances(path: str | Path | None = None, records: list[dict] | None = None):
    """The instance table as a pandas DataFrame, built from the same records."""
    import pandas as pd

    if records is None:
        records, _ = build_instance_records(path)
    df = pd.DataFrame.from_records(records)
    for step in FUNNEL_STEPS:
        df["ts_" + step] = pd.to_datetime(df["ts_" + step], utc=True, format="ISO8601")
    return df


def load_events(path: str | Path | None = None):
    """The raw deduplicated event log as a DataFrame.

    Only the notebook's data-quality section needs this; it is the expensive
    read, so nothing else should call it.
    """
    import pandas as pd

    path = Path(path) if path is not None else data_path()
    events = pd.read_csv(path, dtype={
        "event_id": "string", "tasker_id": "category", "project_id": "category",
        "project_name": "category", "event_name": "category", "device": "category",
        "tasker_tenure": "category", "country": "category", "likeness_variant": "category",
        "prior_projects_completed": "int8", "concurrent_psos": "int8",
        "assessment_est_minutes": "int8",
    })
    events = events.drop_duplicates(subset="event_id").reset_index(drop=True)
    events["event_ts"] = pd.to_datetime(events["event_ts"], utc=True, format="ISO8601")
    events["device_clean"] = events["device"].map(DEVICE_MAP).astype("category")
    return events


def load_all(path: str | Path | None = None, check: bool = True):
    """Raw events plus the instance table, validated. Notebook entry point."""
    records, stats = build_instance_records(path)
    if check:
        validate_records(records, stats)
    return load_events(path), build_instances(records=records)


def funnel_table(inst, steps: list[str] | None = None):
    """Counts, step conversion, loss and overall conversion for each funnel step."""
    import pandas as pd

    steps = steps or FUNNEL_STEPS
    reached = pd.Series({s: int(inst["reached_" + s].sum()) for s in steps}, dtype="int64")
    prev = reached.shift(1)
    return pd.DataFrame({
        "reached": reached,
        "step_conversion_pct": (reached / prev * 100).round(1),
        "lost_at_step": (prev - reached),
        "pct_of_allocated": (reached / reached.iloc[0] * 100).round(1),
    })


def validate(events, inst) -> dict:
    """DataFrame-shaped validation, for the notebook."""
    assert len(events) == EXPECTED_EVENTS, (
        f"expected {EXPECTED_EVENTS:,} deduped events, got {len(events):,}")
    assert len(inst) == EXPECTED_INSTANCES, (
        f"expected {EXPECTED_INSTANCES:,} instances, got {len(inst):,}")
    assert events["event_ts"].notna().all(), "unparsed timestamps"
    assert bool(inst["reached_pso_allocated"].all()), "instance with no allocation event"

    violations = {}
    for earlier, later in zip(FUNNEL_STEPS, FUNNEL_STEPS[1:]):
        bad = int((inst["ts_" + later] < inst["ts_" + earlier]).sum())
        if bad:
            violations[f"{later} before {earlier}"] = bad
    assert not violations, f"out-of-order transitions: {violations}"

    return {
        "events_deduped": len(events),
        "instances": len(inst),
        "taskers": events["tasker_id"].nunique(),
        "projects": events["project_id"].nunique(),
        "out_of_order_transitions": 0,
    }


# --------------------------------------------------------------------------
# inference
# --------------------------------------------------------------------------

def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    """Wilson score interval for a proportion. Returns (point, low, high).

    Wilson rather than normal-approximation because several segments here are
    small enough that the normal interval would run outside [0, 1].
    """
    if n == 0:
        return (float("nan"),) * 3
    p = k / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return p, max(0.0, centre - half), min(1.0, centre + half)


def two_proportion_z(x1: int, n1: int, x2: int, n2: int) -> dict[str, float]:
    """Two-proportion z-test. Used for the likeness early-vs-late pilot."""
    if n1 == 0 or n2 == 0:
        return {"p1": float("nan"), "p2": float("nan"), "diff": float("nan"),
                "z": float("nan"), "p_value": float("nan")}
    p1, p2 = x1 / n1, x2 / n2
    pooled = (x1 + x2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    z = (p1 - p2) / se if se > 0 else float("nan")
    p_value = math.erfc(abs(z) / math.sqrt(2)) if se > 0 else float("nan")
    return {"p1": p1, "p2": p2, "diff": p1 - p2, "z": z, "p_value": p_value}


def minimum_detectable_effect(p: float, n1: int, n2: int,
                              alpha_z: float = 1.96, power_z: float = 0.84) -> float:
    """Smallest difference in proportions the given arm sizes could detect.

    Needed to say honestly whether a null result means "no effect" or just
    "not powered to see one".
    """
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    return (alpha_z + power_z) * se
