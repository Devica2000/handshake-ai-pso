# PSO Funnel — Findings and Recommendations

Analysis of 53,935 PSO instances across 12 projects, taskers invited 1 June – 31 August 2026,
exported 1 September 2026. Every figure here is an output of `notebooks/01_eda.ipynb` (figures the main sections do not
print are in its appendix) and reproduces on `dashboard.html`.

---

## 1. Recommendation

**Fix the assessment landing step. It is the only place in the funnel where a change of this size
is available, and the people we are losing there are not unqualified — they are blocked.**

Three moves, in the order I would do them:

1. **Make the assessment work on a phone, or hand mobile users a clean way to finish on desktop.**
   Mobile is the largest group of people who open an assessment (7,919 of 16,720, 47.4%; 54.1% of
   those with a device recorded) and converts at 40.1% against 77.8% on desktop. Desktop beats mobile
   inside every one of the 11 projects where device is recorded — by 22.9 to 50.9 points — so it is
   not an artifact of which projects attract which devices.
2. **Pull long assessments under the 40-minute mark, or make them explicitly resumable.** Attempt
   rate is 67–68% for assessments of 30 minutes or less and 43–48% for 40 minutes or more. It is a
   step change, not a slope. Instances that start twice attempt at 74.1% against 56.1% for
   single-start, which suggests coming back later is a path people will use if we give it to them.
3. **Say what the assessment involves before they open it.** Abandoners spend a median of 92 seconds
   and answer nothing. Whatever is on that screen is costing us the decision.

**Size of the prize.** If the mobile–desktop gap is friction and we close half of it (18.8 points
across 7,919 mobile starters), that is roughly **1,490 more assessment attempts and about 840 more
completed PSOs — a 15% increase on the 5,503 we complete today.** The chain is 1,492 extra attempts
× the 64.4% mobile pass rate × the 87.3% of passers who go on to complete. That estimate rests on
one assumption I can check, and it holds: among people who do attempt, mobile users pass at 64.4%
and desktop at 66.7%. The taskers we lose on
mobile are as capable as the ones we keep. We are losing them to an interface, not to the bar.

---

## 2. Where we lose people

| Step | Reached | Step conversion | Lost here | % of allocated |
|---|---:|---:|---:|---:|
| pso_allocated | 53,935 | — | — | 100.0% |
| email_sent | 53,082 | 98.4% | 853 | 98.4% |
| email_delivered | 51,123 | 96.3% | 1,959 | 94.8% |
| email_opened | 29,984 | 58.7% | 21,139 | 55.6% |
| email_clicked | 22,595 | 75.4% | 7,389 | 41.9% |
| pso_accepted | 21,242 | 94.0% | 1,353 | 39.4% |
| confidentiality_agreement_signed | 19,483 | 91.7% | 1,759 | 36.1% |
| assessment_started | 16,720 | 85.8% | 2,763 | 31.0% |
| **assessment_attempted** | **9,653** | **57.7%** | **7,067** | **17.9%** |
| assessment_passed | 6,300 | 65.3% | 3,353 | 11.7% |
| contract_started | 5,929 | 94.1% | 371 | 11.0% |
| contract_finished / pso_completed | 5,503 | 92.8% | 426 | 10.2% |
| first_task_claimed | 3,574 | 64.9% | 1,929 | 6.6% |
| first_task_submitted | 3,093 | 86.5% | 481 | 5.7% |

**The largest raw drop is not the real problem.** `email_delivered → email_opened` loses 21,139,
but 2,311 instances accepted the invitation with no recorded open and 1,701 accepted in-app having
never touched the email. Open tracking relies on a pixel that many mail clients block. That step is part
measurement artifact and nothing in this data separates the two halves, so I would not spend a
quarter on it without better instrumentation first.

**The real problem is the assessment block.** `assessment_started → assessment_attempted` converts
at 57.7%, the worst step in the funnel, measured from server-side events we can trust. Taken as a
whole, **16,720 people open an assessment and 6,300 pass: 62% of everyone who gets that far never
makes it through.** Nothing else in the funnel is close.

**One leak outside the brief.** 5,503 instances complete PSO and only 3,574 ever claim a task —
**1,929 fully onboarded taskers, 35% of everyone we onboard, never do any work.** That is a larger
absolute loss than every contract step combined, and we have already paid the full onboarding cost
for them. The data does not say why. It is worth someone's time.

---

## 3. Why they abandon the assessment

**Of the 7,067 instances that open an assessment and never attempt it, 7,060 — 99.9% — answered
zero questions, after a median of 92 seconds.**

That single fact reframes the problem. Nobody is grinding through a hard assessment and giving up.
People open it, look at it for a minute and a half, and leave. And the median bail-out time is flat
at 86–101 seconds across *every* assessment length from 15 to 60 minutes — if length caused fatigue
that number would climb. This is a bounce on the landing screen, before the work starts.

Two things predict the bounce, and they are independent:

**Device — the larger effect.**

| | Attempt rate | Starters |
|---|---:|---:|
| desktop | 77.8% | 5,987 |
| tablet | 59.7% | 724 |
| **mobile** | **40.1%** | **7,919** |

This is not a project-mix artifact. Within each of the 11 projects where device is recorded,
desktop beats mobile by between 22.9 and 50.9 points. There is no project where it reverses. The
gap also sorts cleanly by assessment length: 22.9–31.9 points on the five projects under 40
minutes, 44.1–50.9 points on the six at 40 minutes or more.

**Assessment length — a cliff at 40 minutes.**

| Advertised length | 15 | 20 | 25 | 30 | 40 | 45 | 50 | 55 | 60 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Attempt rate | 68.4% | 67.7% | 67.1% | 67.2% | 42.6% | 46.0% | 46.8% | 45.9% | 47.6% |

Four lengths at 67–68%, five at 43–48%, and almost nothing in between. Because it is a step rather
than a slope, and abandoners leave after about 90 seconds whatever the length, my read is that
people are reacting to the advertised length before they start. Length is fixed per project,
though (§4), so this could also be something else those six projects share.

**They compound.** Mobile's share of starters is a flat 50–59% across every length, so neither
variable stands in for the other:

| | under 40 min | 40+ min |
|---|---:|---:|
| **desktop** | **82.7%** | 73.2% |
| **mobile** | 56.1% | **25.0%** |

A tasker on a phone facing a 45-minute assessment has a one-in-four chance of answering a single
question.

**Ruled out.** Country spans 56.3–58.9% across nine countries. Tenure is 57.1% new vs 58.5%
returning, and prior projects completed is identical to tenure in this data (new always means zero
prior projects). Concurrent PSOs shows no consistent trend: 58.7% at one and 57.0% at two, a dip to
47.1% at three (923 starters), and groups too small to read at four and five (186 and 55) that
point in opposite directions. A story about inexperienced taskers is not what this data shows, and
a story about overloaded taskers has no consistent support either.

---

## 4. What this data does not support

Stating this plainly because the recommendations should be read against it.

- **We cannot see the assessment landing screen.** The 92-second zero-question bounce says the
  decision is made there, but not what on it causes the decision. The fix needs a look at that
  screen, not more of this data.
- **Assessment length cannot be separated from the project.** Each of the 12 projects has exactly
  one `assessment_est_minutes` value, so "long assessments convert worse" and "these six projects
  convert worse" are the same statement here. The length effect is real; its cause is not
  identified. **The device finding does not have this problem** — device varies within every
  project, which is why I weight it more heavily.
- **The device and length findings are observational.** They justify running a test, not skipping
  one.
- **Device is missing for Quartz entirely** (1,835 starters, 100% unrecorded), so all device
  analysis effectively excludes that project. In total 2,090 starters have no device recorded.
- **There is no `assessment_failed` event.** Failure is inferred as attempted-minus-passed, and
  `score` appears only on passes (minimum 0.67). We cannot see how near-misses scored, so I cannot
  say whether the bar is calibrated correctly.
- **The last two weeks are right-censored.** p90 from allocation to completion is 7.8 days against
  a 1 September extract, so late-August cohorts have not finished rather than failed. Excluding
  them moves end-to-end completion from 10.2% to 10.7% — real, but it does not change any
  conclusion.
- **Nothing here says why anyone declined the likeness agreement.**

---

## 5. How we would know it worked

Run it as an A/B test, not a before-and-after. The funnel is stable enough week to week
(acceptance held at 38.7–40.5% every week for the thirteen weeks from June 1 to the week of
August 24) that a before/after would be tempting, but it cannot separate the change from project mix.

| | Metric | Why |
|---|---|---|
| **Primary** | `assessment_started → assessment_attempted`, split by device and length | The step the change targets. Current baseline 57.7% overall, 40.1% mobile. |
| **Guardrail** | `assessment_attempted → assessment_passed` and mean score | Catches "we made it easier to start by making it easier to pass". Baseline 65.3%, mean score 0.81. |
| **Guardrail** | First-task quality / early churn | Catches admitting people who cannot do the work. |
| **End-to-end** | `pso_completed` and `first_task_submitted` per allocation | The only numbers that mean delivered capacity. Baselines 10.2% and 5.7%. |

Two practical notes. **Wait 7+ days per cohort before reading deep-funnel results** — that lag is
already visible in this data and will mislead anyone who reads it early. And **power the test on
the primary metric**: this data has 7,919 mobile starters over three months. A mobile-only 50/50
test gets about 1,320 starters per arm per month, enough to detect a 5.3-point change on the 40.1%
baseline; three months (about 3,960 per arm) gets that down to 3.1 points. That is fine for the
primary metric and far too small to read `pso_completed` directly.

---

## 6. Where the likeness agreement should go

**Put it early — immediately after the invitation is accepted, before the confidentiality
agreement.**

The pilot on Lumen, Orchid and Vesper is a randomised A/B split roughly 50/50 within each project:
6,087 instances in `early` (`after_accept`) against 6,260 in `late` (`with_contract`).

| Metric (% of allocated) | Early | Late | Diff | z |
|---|---:|---:|---:|---:|
| confidentiality_agreement_signed | 30.85% | 36.60% | −5.74pp | −6.75 |
| assessment_attempted | 14.10% | 16.17% | −2.07pp | −3.21 |
| pso_completed | 7.89% | 8.40% | −0.52pp | −1.05 (n.s.) |
| **first_task_submitted** | **5.01%** | **4.92%** | **+0.09pp** | **+0.23 (n.s.)** |

Early looks clearly worse in the middle of the funnel, and both of those gaps are real. But they
close completely by the end: **305 versus 308 taskers actually submitted a first task.** The extra
people late placement carries through the middle do not become productive taskers.

What separates the two options is what the loss costs us:

- **Late: all 52 decliners had already passed the assessment.** Every one of them consumed a full
  qualification cycle — a 30-, 45- or 55-minute assessment on these three projects — and was then lost at
  the final gate, when a customer was already expecting the capacity.
- **Early: zero of the 283 decliners had touched the assessment.** They told us no before anyone
  spent anything.

Asking early converts an expensive late loss into a cheap early one at no cost to delivered output.
It also gets the consent question in front of people at the moment they are deciding whether they
want the project at all, which is where it belongs.

**Three caveats I would raise before anyone over-reads this.** With 6,087 and 6,260 per arm at an
8.15% completion rate the pilot could only detect a difference of about **1.4pp** in completion at
80% power — "no difference" means "none big enough to matter", not zero. The early arm is also
slightly behind *before* the likeness step: 1.69 points fewer accepts (z = −1.92, p = 0.054) and
1.46 fewer email clicks (p = 0.10). Those steps come before either placement, so that gap is
chance or something in the invitation, not the agreement itself, and part of the mid-funnel gap
above is not caused by the step. And the gate-level decline
rates (12.3% early, 8.0% late) are **not** comparable: the late arm only ever asks people who
already survived the assessment, so it is measuring a pre-selected group. The honest read of the
true non-consent rate is the early arm's 12.3%, and we should plan capacity on that number.

---

## 7. Assumptions

1. The unit of analysis is a **PSO instance**, `(tasker_id, project_id)` — 53,935 of them across
   30,025 taskers. Taskers run up to six PSOs at once at different stages, so tasker-level rates
   would be wrong.
2. A step counts as reached if the event **ever** appears for that instance, so the funnel is
   monotonic by construction. 2,470 instances reach a step after `email_opened` without a recorded
   open (2,311 of them accepted); those are tracking gaps, not time travel.
3. **3,121 rows were dropped** as exact duplicates — byte-identical on all 14 columns including
   `event_id`. Treated as a pipeline replay. This is why raw event counts run higher than the
   funnel (54,473 raw `pso_allocated` rows vs 53,935 allocated instances; the 538 difference is all
   replays). The only genuine repeat event is a second `assessment_started`, on 1,479 instances.
4. `device` was collapsed from ten raw values (mixed casing, OS and form factor) to desktop /
   mobile / tablet, and taken at the earliest `assessment_started` that recorded one.
5. Headline figures use **all** instances. The maturity filter (7+ days before extract) is
   available on the dashboard and moves completion from 10.2% to 10.7%.
6. No `assessment_failed` event exists, so "failed" means attempted and not passed.
