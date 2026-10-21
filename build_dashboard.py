"""Build dashboard.html: a single self-contained file that opens by double-click.

Collapses the 312k-row event log into one row per PSO instance, encodes those
rows as base64 typed arrays, and inlines them into src/dashboard_template.html.
No server, no CDN, no network — the whole thing is one file on disk. Standard
library only, so it runs in seconds in a few tens of megabytes.
"""

from __future__ import annotations

import base64
import json
import sys
from array import array
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))

import pso_clean as pc  # noqa: E402

TEMPLATE = ROOT / "src" / "dashboard_template.html"
OUTPUT = ROOT / "dashboard.html"

DEVICE_ORDER = ["desktop", "mobile", "tablet", "unknown"]
VARIANT_ORDER = ["none", "early", "late"]

TYPECODE = {"u8": "B", "u16": "H", "u32": "I"}


def encode(values: list[int], kind: str) -> dict[str, str]:
    buf = array(TYPECODE[kind], values)
    if sys.byteorder == "big":  # the browser reads these as little-endian
        buf.byteswap()
    return {"type": kind, "data": base64.b64encode(buf.tobytes()).decode("ascii")}


def codes_for(records: list[dict], field: str, order: list) -> list[int]:
    lookup = {v: i for i, v in enumerate(order)}
    out = []
    for r in records:
        v = r[field]
        if v not in lookup:
            raise AssertionError(f"unmapped {field} value: {v!r}")
        out.append(lookup[v])
    return out


def build_payload(records: list[dict]) -> dict:
    all_steps = pc.FUNNEL_STEPS + pc.LIKENESS_STEPS

    # One 32-bit mask per instance: a bit per step, plus a maturity bit on top.
    mask = []
    for r in records:
        m = 0
        for bit, step in enumerate(all_steps):
            if r["reached_" + step]:
                m |= 1 << bit
        if r["mature"]:
            m |= 1 << len(all_steps)
        mask.append(m)

    project_labels = sorted({r["project_name"] for r in records})
    country_labels = sorted({r["country"] for r in records})
    tenure_labels = sorted({r["tasker_tenure"] for r in records})
    est_values = sorted({r["assessment_est_minutes"] for r in records})
    conc_values = sorted({r["concurrent_psos"] for r in records})
    week_labels = sorted({r["alloc_week"] for r in records})

    long_est_index = next(i for i, m in enumerate(est_values)
                          if m >= pc.LONG_ASSESSMENT_MINUTES)

    for r in records:
        r["_device"] = r["assessment_device"] or "unknown"
        r["_variant"] = r["likeness_variant"] or "none"

    def clip(v, hi):
        return 0 if v is None else max(0, min(int(v), hi))

    columns = {
        "mask": encode(mask, "u32"),
        "project": encode(codes_for(records, "project_name", project_labels), "u8"),
        "device": encode(codes_for(records, "_device", DEVICE_ORDER), "u8"),
        "country": encode(codes_for(records, "country", country_labels), "u8"),
        "tenure": encode(codes_for(records, "tasker_tenure", tenure_labels), "u8"),
        "est": encode(codes_for(records, "assessment_est_minutes", est_values), "u8"),
        "concurrent": encode(codes_for(records, "concurrent_psos", conc_values), "u8"),
        "week": encode(codes_for(records, "alloc_week", week_labels), "u8"),
        "variant": encode(codes_for(records, "_variant", VARIANT_ORDER), "u8"),
        "session": encode([clip(r["assessment_session_seconds"], 65535) for r in records], "u16"),
        "questions": encode([clip(r["assessment_questions_answered"], 255) for r in records], "u8"),
        "starts": encode([clip(r["assessment_starts"], 255) for r in records], "u8"),
    }

    return {
        "n": len(records),
        "steps": pc.FUNNEL_STEPS,
        "likeness_steps": pc.LIKENESS_STEPS,
        "email_tracking_steps": pc.EMAIL_TRACKING_STEPS,
        "long_est_index": long_est_index,
        "lookups": {
            "project": project_labels,
            "device": DEVICE_ORDER,
            "country": country_labels,
            "tenure": tenure_labels,
            "est": [f"{m} min" for m in est_values],
            "concurrent": [str(c) for c in conc_values],
            "week": week_labels,
            "variant": VARIANT_ORDER,
        },
        "columns": columns,
        "headline": HEADLINE,
        "quality_notes": QUALITY_NOTES,
    }


HEADLINE = (
    "<b>The drop that matters is the assessment.</b> 16,720 instances open a qualification "
    "assessment and only 9,653 ever answer a question — a 57.7% step conversion, the worst in the "
    "funnel. Of the 7,067 who walk away, <b>7,060 answered zero questions</b>, after a median of "
    "92 seconds. Two things predict it: assessments of 40+ minutes (attempt rate 43–48% vs 67–68% "
    "below that) and mobile (40.1% vs 77.8% on desktop; mobile is 47.4% of starters). Country, "
    "tenure and prior projects do not move it, and concurrent PSOs shows no consistent trend."
)

QUALITY_NOTES = [
    {
        "level": "warn",
        "title": "3,121 duplicate rows were dropped",
        "body": "The export contained 3,121 rows byte-identical to another row on all 14 columns, "
                "duplicate <code>event_id</code> included — a pipeline replay, not two real events. "
                "Every number here is computed after de-duplication (312,148 rows).",
    },
    {
        "level": "warn",
        "title": "Email opens and clicks are undercounted",
        "body": "2,311 instances accepted the invitation with no recorded <code>email_opened</code>, and "
                "1,701 with no recorded <code>email_clicked</code>. The 1,701 are exactly the instances "
                "that accepted in-app: all had the email delivered and 503 opened it, but none used its "
                "link. The open undercount shows among those who accepted through the email: every one "
                "clicked its link, yet 1,113 have no recorded open. Open tracking relies on a pixel that "
                "many mail clients block. The "
                "<code>email_delivered → email_opened</code> step shows the largest raw drop in the funnel "
                "(21,139), but it is part measurement artifact and nothing in this data separates the two. "
                "It is excluded from the \"worst step\" comparison for that reason.",
    },
    {
        "level": "warn",
        "title": "The last two weeks are right-censored",
        "body": "The export is dated 1 September. Median time from allocation to PSO completion is 2.6 days "
                "and p90 is 7.8 days, so instances allocated in late August have not finished yet rather than "
                "failed. Completion falls from a steady 9.9–12.6% to 6.7% and then 0.1% purely for this reason. "
                "Use the <b>mature cohorts only</b> filter to exclude them; the dashboard defaults to showing "
                "everything so its headline figures reconcile with the written analysis.",
    },
    {
        "level": "warn",
        "title": "Assessment length cannot be separated from the project",
        "body": "Each of the 12 projects has exactly one <code>assessment_est_minutes</code> value, so "
                "\"long assessments convert worse\" and \"these six projects convert worse\" are the same "
                "statement in this data. The length effect is real but its cause is not identified. "
                "The device effect does not have this problem — device varies within every project.",
    },
    {
        "level": "warn",
        "title": "The device column was normalised",
        "body": "<code>device</code> arrived with ten values mixing casing, OS and form factor "
                "(<code>mobile</code>/<code>Mobile</code>/<code>iOS</code>/<code>Android</code> are all "
                "one thing). They are collapsed to desktop / mobile / tablet. The column is null on "
                "server-side events, so device here is the device at the earliest "
                "<code>assessment_started</code> that recorded one; instances that never started an "
                "assessment show as <code>unknown</code>.",
    },
    {
        "level": "warn",
        "title": "Quartz records no device at all",
        "body": "All 1,835 Quartz instances that started an assessment have an unrecorded device, so "
                "every device comparison here effectively excludes that project. In total 2,090 starters have "
                "no device recorded. The device finding still holds inside each of the other eleven "
                "projects individually, by between 22.9 and 50.9 points.",
    },
    {
        "level": "warn",
        "title": "There is no assessment_failed event",
        "body": "Failure is inferred as attempted-minus-passed, and <code>score</code> only appears on "
                "passes (minimum 0.67). We cannot see how near-miss candidates "
                "scored, which limits any claim about whether the assessment is correctly calibrated.",
    },
    {
        "level": "warn",
        "title": "What this data cannot answer",
        "body": "Nothing here shows what the assessment landing screen actually says or looks like, why "
                "mobile users bounce, whether <code>assessment_est_minutes</code> is an accurate estimate, "
                "or why anyone declined the likeness agreement. The device and length findings are "
                "observational, not experimental — they are strong enough to justify a test, not to skip one.",
    },
]


def main() -> None:
    records, stats = pc.build_instance_records(ROOT / pc.DATA_FILE)
    print(pc.validate_records(records, stats))

    payload = build_payload(records)
    data_json = json.dumps(payload, separators=(",", ":"))

    template = TEMPLATE.read_text()
    assert "__PSO_DATA__" in template, "template is missing the __PSO_DATA__ placeholder"
    OUTPUT.write_text(template.replace("__PSO_DATA__", data_json))

    size_mb = OUTPUT.stat().st_size / 1_000_000
    print(f"wrote {OUTPUT} — {size_mb:.2f} MB, {payload['n']:,} instances")


if __name__ == "__main__":
    main()
