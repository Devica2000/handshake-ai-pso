# Journal — how I worked through the PSO case

This is the story of how I approached the problem: what I looked at, in what order, and why each
step led to the next. The conclusions are written up in `FINDINGS.md`. Every number here is an
output of `notebooks/01_eda.ipynb`; the ones its main sections do not print are in its appendix.

---

## 1. Framing the problem

The brief asks three things: where we lose people during Project-Specific Onboarding (PSO), why,
and where a new likeness agreement should go. Before touching the data I re-read one line in it:
*"every tasker we lose is capacity a customer is waiting on."* That told me what "success" means
here. A tasker who finishes PSO but never does any work has not delivered capacity, so I decided
to follow every question all the way to `first_task_submitted`, not stop at `pso_completed`. That
decision ends up mattering for the likeness recommendation.

The PSO steps, as the brief describes them: an invitation, a confidentiality agreement, a
qualification assessment, and a work contract. The data is an event export for taskers invited
between June 1 and August 31, 2026, extracted on September 1, "as it came out of the pipeline" —
which I read as a hint not to trust it before checking it.

---

## 2. Getting to know the data before trusting it

**I started by reading every column and asking what one row of my analysis should be.** The file
has 315,269 rows of events across 14 columns. Each tasker can be invited to several projects, so
my first question was whether a tasker can sit at different funnel steps on different projects. I
checked: 30,025 taskers hold 53,935 (tasker, project) pairs, 14,344 taskers have more than one, and
one tasker has six. Each pair progresses on its own. So I chose the **PSO instance — one
(tasker_id, project_id) pair — as the unit of analysis**. Using the tasker would blur together
someone who finished one project and abandoned another.

**I checked for duplicates, because a raw pipeline export usually has them.** 3,121 rows repeat an
`event_id`, and every one of them is byte-identical to an earlier row on all 14 columns. Two real
events would at least differ in timestamp, so I treated these as a pipeline replay and dropped
them, leaving 312,148 events.

Later I noticed that the raw event counts did not match my funnel — 54,473 `pso_allocated` rows in
the raw file, but 53,935 allocated instances — so I went back and reconciled every event three
ways: raw rows, rows after de-duplication, and instances that reached the step. The 538-row gap on
allocation is entirely replays. Across all events, the differences are 3,121 replayed rows plus
1,479 genuine second `assessment_started` events, which are real return visits days apart. No
other step ever happens twice for the same instance. That gave me confidence the funnel is
unaffected by duplicates: a step is either reached or not, and a replayed row cannot change that.

**I cleaned the one messy column.** `device` has 10 raw values that mix casing, operating system
and form factor (`mobile`, `Mobile`, `iOS`, `Android` are all the same thing). I collapsed them to
desktop / mobile / tablet. Device is null on 189,801 rows, about 60% of the file, because it is
only captured on interactive events, not server-side ones like `email_delivered`.

**I checked the timestamps before relying on the step order.** All of them fall inside June 1 –
August 31, and across all 53,935 instances no step is ever recorded before the step that precedes
it. So I could order the funnel by step definition and did not need to repair any sequences.

**I checked which attributes belong to the tasker and which to the event.** Country never varies
within a tasker (9 countries, US is 42.6% of instances). Tenure and prior projects completed turn
out to be the same thing: every "new" tasker has 0 prior projects and every "returning" one has
at least 1. And each of the 12 projects has exactly one advertised assessment length, between 15
and 60 minutes. That last fact became an important limitation later.

**Finally I looked inside the `properties` JSON**, since its keys differ by event type. Most of it
has no variation to analyse: every invitation uses the same template (`pso_invite_v3`) and every
click the same call to action (`view_project`). Three keys turned out to matter:
`source` on `pso_accepted` (email vs in-app), `session_seconds` and `questions_answered` on
`assessment_started`, and `placement` on the likeness agreement.

---

## 3. Finding the drop that matters

**I built the funnel by counting how many instances ever reached each step.** 53,935 allocated
end up as 5,503 completed PSOs (10.2%) and 3,093 first tasks submitted (5.7%).

**My first candidate was the largest raw drop, and I decided not to trust it.** Email delivered →
opened loses 21,139 instances, by far the biggest number. Before treating it as the problem I
wanted to know whether that step is even measured reliably, so I counted people who accepted the
invitation without a recorded open. There are 2,311 of them, and 1,701 accepted in-app without
touching the email at all (2,470 instances reach some later step with no recorded open). Open
tracking relies on a pixel that many mail clients block, so this step is part real loss and part
missed tracking, and nothing in the data separates the two. I set it aside rather than build a
recommendation on it.

**So I ranked the steps by conversion rate on events I could trust.** The worst is assessment
started → attempted: 57.7% conversion, 7,067 instances lost. Looking at the assessment as a
whole, 16,720 people open it and 6,300 pass, so 62% of everyone who gets that far never makes it
through. Nothing else in the funnel comes close. This is the drop I focused on.

---

## 4. Digging into why people abandon the assessment

**First I wanted to know what abandoners actually did before leaving.** The `properties` on
`assessment_started` record how long the session lasted and how many questions were answered. Of
the 7,067 who opened the assessment and never attempted it, 7,060 (99.9%) answered zero
questions, and their median session was 92 seconds. People who did attempt spent a median of
1,778 seconds and answered 13 questions. So nobody is struggling through and giving up. People
open the assessment, look at it for a minute and a half, and leave.

**Then I tested the obvious explanation, fatigue.** If longer assessments wore people down, the
time before quitting should rise with length. I plotted the median session length of abandoners
against the advertised length, and it is flat at 86–101 seconds from 15 to 60 minutes. That
pointed me at the landing screen, before any work begins, rather than at the questions.

**Next I segmented the starters by every attribute I had, to see what predicts the bounce.** Two
things stood out:

- **Device.** Desktop attempts at 77.8%, tablet 59.7%, mobile 40.1%. Mobile is the largest group:
  7,919 of the 16,720 starters (47.4%, or 54.1% of those with a device recorded).
- **Assessment length.** 15–30 minute assessments sit at 67–68%; 40–60 minute ones at 43–48%. It
  is a step at 40 minutes, not a gradual slope.

And several things did not: country (56.3–58.9% across nine countries), tenure (57.1% new vs
58.5% returning) and therefore prior projects. Concurrent PSOs shows no consistent pattern — 58.7%
at one and 57.0% at two, a dip to 47.1% at three (923 starters), and groups too small to read at
four and five that point in opposite directions — so I did not treat it as a driver. I think the
non-drivers are worth saying out loud, because "inexperienced" or "overloaded" taskers are the
stories people would reach for first.

**Then I asked whether device and length were really two separate effects**, or one standing in
for the other. Mobile's share of starters is a flat 50–59% at every assessment length, so neither
is a proxy for the other. Crossing them, they compound:

| | under 40 min | 40+ min |
|---|---:|---:|
| desktop | 82.7% | 73.2% |
| mobile | 56.1% | 25.0% |

A tasker on a phone facing a 40+ minute assessment has about a one-in-four chance of answering a
single question.

**Then I worried the device effect might really be a project effect** — maybe some projects just
attract more mobile users and also convert worse. So I checked the gap inside each project.
Desktop beats mobile in all 11 projects where device is recorded, by 22.9 to 50.9 points, and
never the other way round. The gap is about twice as large on the six 40+ minute projects
(44.1–50.9 points) as on the five shorter ones (22.9–31.9), which is the compounding again.

**I could not do the same check for length**, because each project has exactly one length. "Long
assessments convert worse" and "these six projects convert worse" are the same statement in this
data. I still report the length effect, but I weight the device finding more heavily for that
reason.

**One more thing I noticed:** 1,479 instances started the assessment twice, and they go on to
attempt at 74.1% against 56.1% for those who started once. That is correlational — people who come
back were probably more motivated anyway — but it suggests coming back later is a path people will
take if we make it easy.

---

## 5. Sizing it before recommending anything

**Before calling the mobile gap "friction", I checked whether the people we lose on mobile are
simply less capable.** If they were, making the assessment easier to start on a phone would just
let in people who fail. Among those who do attempt, mobile users pass at 64.4% and desktop at
66.7%. They are about as capable. We seem to be losing them to the interface, not to the bar.

That let me size the opportunity. If we closed half of the desktop–mobile gap (18.8 points across
7,919 mobile starters), that is about 1,492 extra attempts. Carried through the 64.4% mobile pass
rate and the 87.3% of passers who go on to complete, it is about 839 more completed PSOs — a 15.2%
increase on the 5,503 we complete today.

---

## 6. Making sure the calendar was not fooling me

The export is dated September 1, so anyone invited in late August has not had time to finish. I
checked how long each step takes: the median time from allocation to completion is 2.64 days and
the 90th percentile is 7.80 days. Then I looked at outcomes by allocation week. Completion sits at
9.9–12.6% every week through the week of August 17, then falls to 6.7% and 0.1% — exactly what
missing time, not worse taskers, would look like. Acceptance stays at 38.7–40.5% through the week
of August 24, because accepts happen within a day.

Excluding instances allocated in the last 7 days (48,934 of 53,935 remain) moves end-to-end
completion from 10.2% to 10.7%. The effect is real but small, and it does not change any
conclusion. I kept the headline numbers on all instances and put the 7-day filter on the
dashboard as a toggle, off by default so its opening numbers match the write-up.

---

## 7. A leak I found outside the brief

Following the funnel to the end, 5,503 instances complete PSO but only 3,574 ever claim a task.
**1,929 fully onboarded taskers — 35% of everyone we onboard — never do any work.** That is a larger
loss than both contract steps combined (371 + 426), and it happens after we have paid the full
onboarding cost. The data does not tell me why, so I flag it rather than explain it.

---

## 8. The likeness agreement

**First I made sure I understood what the pilot was.** `likeness_variant` appears on three
projects (Lumen, Orchid, Vesper) and splits each roughly 50/50 into `early` and `late`: 6,087
versus 6,260 instances. The `placement` key on signed agreements tells me what those mean: every
early signature is `after_accept` (2,017) and every late one is `with_contract` (598). So `early`
means right after accepting the invitation, before the confidentiality agreement; `late` means at
the very end.

**Then I compared the two arms step by step.** In the middle of the funnel, early looks clearly
worse: 5.74 points fewer confidentiality agreements (z = −6.75) and 2.07 points fewer assessment
attempts (z = −3.21). If I had stopped there, I would have recommended late placement.

**But because I had decided to follow everything to delivered work, I kept going.** By the end the
gap closes. PSO completion differs by 0.52 points (z = −1.05, not significant), and first tasks
submitted are a dead heat: 305 versus 308 taskers (z = +0.23). The extra people that late placement
carries through the middle do not become productive taskers.

**So the question became: what does each kind of loss cost?** I looked at what decliners had
already done before declining. In the late arm, all 52 decliners had already passed the assessment,
so every one of them went through a full qualification before we lost them. In the early arm, none
of the 283 decliners had started it. Asking early turns an expensive late loss into a cheap early
one, at no cost to delivered output. **My recommendation is to place it early, right after the
invitation is accepted.**

**Caveats I checked for myself before recommending it:**

- **Power.** At a baseline completion of 8.15%, the pilot could only detect a difference of about
  1.38 points at 80% power. "No difference" means "none big enough to matter", not zero.
- **A small imbalance before the treatment.** The early arm is already 1.69 points behind on
  acceptance (p = 0.054) and 1.46 points behind on email clicks (p = 0.10). Those steps happen
  before either placement, so that gap is chance or something in the invitation, not the agreement,
  and some of the mid-funnel gap is not caused by the step.
- **The decline rates are not comparable.** Early is 12.3% (283 of 2,300) and late 8.0% (52 of 650),
  but the late arm only asks people who already survived the assessment. The early arm's 12.3% is
  the better estimate of how many people will not consent, and it is the number I would plan
  capacity on.

---

## 9. How we would know the assessment fix worked

I would run it as an A/B test, not a before-and-after, because project mix shifts over time. The
primary metric is assessment started → attempted, split by device and length (57.7% overall,
40.1% on mobile today). The guardrails are attempted → passed and the mean score (65.3% and 0.81
today), to catch "we made it easier to start by making it easier to pass", plus first-task quality.
The end-to-end metrics are PSO completion and first task submitted per allocation (10.2% and 5.7%).

On sizing: this data has 7,919 mobile starters over three months. A mobile-only 50/50 test gets
about 1,320 per arm per month, enough to detect a 5.3-point change; three months (about 3,960 per
arm) gets that to 3.1 points. That is enough for the primary metric, not for completion, and deep-
funnel results should only be read for cohorts at least 7 days old.

---

## 10. What I would do next with more time or data

- **Look at the assessment landing screen itself.** The data tells me the decision is made in
  about 90 seconds on that screen, but not what on it drives the decision.
- **Separate length from project**, ideally by testing a shorter or resumable version of one long
  assessment.
- **Fix email open tracking** before anyone draws conclusions from the open step.
- **Find out why 35% of onboarded taskers never claim a task.**
- **Capture device on Quartz**, which records none for any of its 1,835 starters.

---

## Appendix A — Column reference

| Column | What I found |
|---|---|
| `event_id` | Unique per event, except 3,121 byte-identical replayed rows |
| `tasker_id` | 30,025 distinct taskers |
| `project_id` / `project_name` | 12 projects, one name each |
| `event_name` | 17 values: 15 funnel steps + 2 likeness events |
| `event_ts` | ISO-8601 UTC, all within June 1 – August 31, no out-of-order steps |
| `device` | 10 raw values mixing casing, OS and form factor; null on ~60% of rows (server-side events) |
| `tasker_tenure` | new / returning; identical to `prior_projects_completed` = 0 vs > 0 |
| `prior_projects_completed` | 0–10 |
| `country` | 9 countries, US 42.6% of instances; never varies within a tasker |
| `concurrent_psos` | 1–5 |
| `assessment_est_minutes` | 15–60; exactly one value per project |
| `likeness_variant` | early / late, only on the three pilot projects |
| `properties` | JSON whose keys differ by event type (see §2) |

## Appendix B — Assumptions I made

1. **The unit is the PSO instance**, (tasker_id, project_id), not the tasker.
2. **A step counts as reached if its event ever appears** for that instance, so the funnel only
   ever goes down. This is why the 2,470 instances with a missing `email_opened` do not break it.
3. **The 3,121 repeated `event_id` rows are pipeline replays**, not real events, and are dropped.
4. **Device is taken from the earliest `assessment_started` that recorded one**, after collapsing
   the 10 raw values to desktop / mobile / tablet.
5. **Headline figures use all instances.** The 7-day maturity filter is a dashboard toggle and moves
   completion from 10.2% to 10.7%.
6. **"Failed" means attempted and not passed.** There is no `assessment_failed` event, and `score`
   is only recorded on passes (minimum 0.67).
7. **Email open and click are excluded from the "worst step" comparison**, because their drops are
   partly missed tracking and the data cannot separate the two.
