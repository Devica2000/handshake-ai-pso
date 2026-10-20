# PSO Onboarding Funnel — Handshake AI Data Science case study

Where we lose taskers during Project-Specific Onboarding, why, what to do about it, and where the
likeness agreement should go.

> The case-study PDF and the raw event export are not included in this repo (see `.gitignore`).
> `dashboard.html` is self-contained and runs without them; only `build_dashboard.py` and the
> notebook need the original CSV.

## Suggested reading order

| | File | What it is |
|---|---|---|
| 1 | **`FINDINGS.md`** | The answers: where we lose people, why, what to do, how we'd know it worked, and where the likeness agreement should go. |
| 2 | **`dashboard.html`** | The interactive funnel, to back up the findings and explore your own questions. |
| 3 | `Journal.md` | How I worked through the problem, in order, and the reasoning behind each decision. |
| 4 | `notebooks/01_eda.ipynb` | The working. Every number in `FINDINGS.md` and `Journal.md` is an output of this notebook; figures the main sections do not print are in its appendix. |

## Run the dashboard

**Double-click `dashboard.html`**, or from a terminal in this folder:

```bash
open dashboard.html        # macOS
xdg-open dashboard.html    # Linux
```

It is one self-contained file: no server, no build step, no internet connection. It holds all
53,935 PSO instances (~1.2 MB) and recomputes the funnel in the browser as you filter, so you can
slice it any way you like rather than only the ways I anticipated.

- **Funnel** — the whole funnel with step conversion, loss per step, and a table view.
- **Assessment drop-off** — the evidence for the main finding.
- **Compare any segment** — pick any step transition and split it by any dimension, with 95%
  Wilson intervals. This is the tab for answering your own questions.
- **Likeness pilot** — the early-vs-late A/B with two-proportion z-tests.
- **Data quality** — every caveat, stated where it applies.

Filters compose, tabs are linkable (`dashboard.html#assessment`), and there is a light/dark toggle.

## Headline

The biggest *trustworthy* drop is `assessment_started → assessment_attempted`: 7,067 instances
lost at 57.7% conversion. **7,060 of them answered zero questions, after a median of 92 seconds** —
a landing-screen bounce, not a difficulty problem. Mobile (40.1% vs 77.8% desktop) and assessments
of 40+ minutes (43–48% vs 67–68%) each predict it, and they compound to 25.0% for mobile users on
a long assessment.

The largest *raw* drop, `email_delivered → email_opened`, is partly a measurement artifact and is
called out as such throughout.

The likeness agreement should go **early, right after the invitation is accepted**: delivered
output is the same either way (305 vs 308 first tasks submitted), but every late-arm decliner had
already passed the assessment.

## Rebuild from source

Needs `pso_funnel_events - pso_funnel_events.csv` in the repo root.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt

.venv/bin/python build_dashboard.py          # regenerates dashboard.html
```

Then open `notebooks/01_eda.ipynb` and run all cells.

## How it fits together

```
src/pso_clean.py              one implementation of the funnel logic
  ├── build_instance_records()  de-duplicates events and builds one record per PSO instance
  ├── raw_quality_report()      the data-quality counts on the raw file
  ├── build_instances()         thin pandas wrapper for the notebook
  └── wilson / two_proportion_z / minimum_detectable_effect
         │
         ├──> notebooks/01_eda.ipynb     the analysis
         └──> build_dashboard.py  ──>  src/dashboard_template.html  ──>  dashboard.html
```

Both the notebook and the dashboard import `pso_clean`, so their numbers cannot drift apart.
