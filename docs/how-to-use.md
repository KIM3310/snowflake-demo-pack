# How to Use This Pack

A Solution Engineer's field guide to running the demos in customer conversations.

## Before a customer call

1. **Pick the right demo.** Match the industry to the customer. If they're outside the five, pick the closest analog (regtech → finance, hospitality → retail, aerospace → manufacturing, pharma → healthcare, gaming → media).
2. **Pre-load the demo** in your Snowflake account. Run `make setup && make demo-<industry>` at least 24 hours before the call so Dynamic Tables are populated and query history is primed.
3. **Read the `value-case.md`** for the chosen demo. Internalize the 3-bullet elevator pitch — you'll need it in the first 60 seconds.
4. **Read the `presentations/<industry>-5min-pitch.md`**. It's the delivery script; customize the opening anchor to the specific customer's language.
5. **Pre-open 3 browser tabs** side-by-side:
   - Snowflake worksheet with the `04-analytics.sql` file pre-loaded.
   - Streamlit dashboard (`streamlit run 05-dashboard.py`) already running.
   - The `architecture.md` rendered so you can walk the mermaid diagram.
6. **Charge your laptop fully.** Running a live demo on 4% battery at a customer is a career-limiting move.

## During the call

### The 5-minute delivery structure

Every demo follows the same structure, reflected in the 5-minute pitch scripts:

1. **0:00-0:30 — Anchor the customer's problem.** Use their language, their numbers.
2. **0:30-1:15 — Walk the architecture.** One mermaid diagram, one minute.
3. **1:15-2:30 — Live query walk-through.** 3 queries, in this order: simplest, business-value, killer moment.
4. **2:30-3:15 — The differentiator moment.** The feature the customer's incumbent can't match.
5. **3:15-4:15 — TCO framing.** The table in the pitch script.
6. **4:15-4:45 — POC offer.** Concrete, scoped, time-boxed.
7. **4:45-5:00 — The ask.** Who should I talk to next?

### Live-query discipline

- **Never live-type queries.** Always execute from a pre-loaded worksheet. Typing in a customer call is how you demo your typos.
- **Read query output aloud.** The customer watching your screen shouldn't have to parse — you tell them what to see.
- **Know the expected numbers.** If a query returns unexpected results (pipeline lagged, Dynamic Table refreshing), have a fallback answer ready.
- **Fail gracefully.** If a query errors during a demo, say: "let me pull the result from yesterday's run so we keep the conversation moving." Have screenshots available.

## After the call

1. **Send the `value-case.md`** as a PDF follow-up within 4 hours.
2. **Record the objections** in your CRM. Over 10 customers you'll see the pattern — feed it back into the `presentations/*-pitch.md` objection banks.
3. **Attach a POC scope document.** Use the POC offer template from the pitch script.
4. **Schedule the next session** before ending the call. "I'll send a calendar invite for Thursday."

## Customization tips

### Per-customer branding

Fork the demo repo for the customer. Change:
- Demo database name (`SNOWFLAKE_DEMO_PACK` → `<CUSTOMER>_POC_PILOT`).
- Data generator parameters to match the customer's volume order-of-magnitude.
- Role names to match the customer's existing IAM groups (if provided ahead of time).
- Streamlit branding (title, color, logo).

### Customer-specific data

Never run a demo on real customer data during the pre-sales phase. Use synthetic data that matches their schema. If they insist on seeing their data, that's a signal to transition to a formal POC with proper security review.

### Regional pricing adjustments

The cost estimates in `docs/cost-estimates.md` are for US-East commercial regions. Multiply by your regional multiplier (typically 1.0-1.4x for APAC, 1.0-1.2x for EU).

## When the demo breaks

Common failure modes and recoveries:

| Failure | Recovery |
|---------|----------|
| Dynamic Table lag exceeds expected window | "This is the target, not the measured. Let me show you the last completed refresh." Show `INFORMATION_SCHEMA.DYNAMIC_TABLE_REFRESH_HISTORY`. |
| Cortex function times out | "Cortex has regional load peaks. Let me show you the cached result." Have a screenshot ready. |
| Streamlit dashboard doesn't load | Switch to a screen recording of the dashboard. Every SE should keep a 60-second MP4 per demo. |
| Your warehouse isn't started | `ALTER WAREHOUSE DEMO_WH RESUME;` and fill 30 seconds explaining the warehouse auto-suspend behavior. |
| Network failure during demo | You should already have the Streamlit dashboard recorded. Pivot to walking the `value-case.md`. |

## When to skip a demo

Not every opportunity needs a demo. Signals that you should not demo:

- The customer has already run a competitive POC and is in late-stage evaluation.
- The conversation is about contract terms, not capability.
- You have less than 15 minutes — that's a discovery call, not a demo.
- The decision-maker isn't in the room. Demo for the buyer, not the champion.

## Feedback loop to this repo

This pack evolves with every customer conversation. Maintain:

- **`presentations/*-pitch.md` objection banks**: add every new objection with your response.
- **`docs/cost-estimates.md`**: real customer consumption data updates the estimates over time.
- **`customization-guide.md`**: every non-trivial customization pattern becomes a reusable tip.

The pack is a reference library. The goal isn't to use it unchanged — the goal is that each adaptation is cheap because the substrate is solid.
