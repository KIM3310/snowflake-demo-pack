# Manufacturing — Predictive Maintenance: 5-Minute SE Pitch

*Delivery script for a pre-sales conversation. Total runtime: 5 minutes.*

---

## 0:00 — 0:30 — Anchor the problem

> "One unplanned line stoppage on a high-volume asset costs between $20K and $200K per hour depending on your industry. Your maintenance team already has IoT sensors on every critical machine — they're drowning in telemetry. The data exists. The question is: can you turn sensor streams into a 72-hour failure warning that the plant manager trusts enough to schedule maintenance on?"

**What to watch**: the operations leader recognizes the specific cost figures. If they push back, substitute their sector's number.

## 0:30 — 1:15 — Show the architecture

Open `demos/03-manufacturing-predictive-maintenance/architecture.md`.

> "Sensor telemetry lands via Snowpipe Streaming into a raw landing layer — we're demoing 100 sensors at 1-second resolution, roughly 8.6M rows per day. Streams and Tasks drive the feature-engineering pipeline. A Snowpark ML forecast model runs inline, emitting probability-of-failure-in-72h. Snowflake Alerts fire when the probability crosses a calibrated threshold, and Native Apps give you the packaging story for exposing this to your OEMs or plant ops teams."

**What to emphasize**: Native Apps is the manufacturing-specific wedge. "You can package this as an installable app for each plant, each OEM partner, without copying data across account boundaries."

## 1:15 — 2:30 — Live query walk-through

Run queries from `04-analytics.sql`:

1. **Per-asset failure probability trend** — the 72-hour forecast curve.
2. **"Maintenance cost avoided" projection** — avoided downtime × cost-per-hour.
3. **False alarm rate by asset class** — the measurable that keeps the plant manager trusting you.

> "Notice query 3. Every predictive-maintenance program lives or dies on false alarm rate. If the model cries wolf, the plant manager stops acting on alerts within 2 weeks. Snowflake's observability stack lets you measure and report on this continuously."

## 2:30 — 3:15 — The Native Apps framing

> "Here's what most customers don't realize is possible. You can publish this entire predictive pipeline as a Snowflake Native App — your plants or OEM partners install it in their Snowflake account. Their sensor data never leaves their boundary. Your model code never leaves your boundary. You monetize the predictive capability as a per-asset license instead of consulting engagements."

**What to emphasize**: if the customer has multi-plant or OEM-partnership ambitions, this changes their business model conversation.

## 3:15 — 4:15 — The TCO framing

| Current state (typical) | This pattern |
|-------------------------|--------------|
| Historian (OSIsoft/Aveva) + Kafka + Spark + ML platform + dashboard | Landing → Streams+Tasks → Snowpark ML → Alerts |
| 5-8 systems, industrial + IT silo | 1 platform, SQL+Python |
| Per-plant pipeline: $250K-$500K build + $120K/yr maintenance | Demo estimates 1.3 credits / 10M events; per-plant marginal cost |
| 15-30 min lag from sensor event to dashboard | 60-second lag |

> "Most manufacturing customers adopt this per-plant. Start with one asset class on one plant. Measure the false alarm rate reduction and the first caught failure. Expand from there."

## 4:15 — 4:45 — Proof-of-concept offer

> "4-week POC. You bring 30 days of historian data for one asset class — we use Kepware or OPC-UA export, whatever you've got. I bring the Snowpark ML pipeline, the alerts wiring, and the per-asset dashboard. At the end, your maintenance team has a 72-hour forecast they can act on. Success criterion: one caught failure or a 30% reduction in false alarms vs your current rule-based system."

## 4:45 — 5:00 — Close with the ask

> "Which plant's maintenance team is most receptive to data-driven operations? That's where the POC goes. Can you make an intro to the plant engineering lead?"

---

## Objection bank

| Objection | Response |
|-----------|----------|
| "Our historian can't be replaced." | "It isn't. Historian stays where it is. Snowflake gets the data via OPC-UA → Kepware → Snowpipe Streaming. The historian keeps its role in OT; Snowflake plays in IT." |
| "IT/OT security boundary." | "Snowpipe Streaming connector can sit in your DMZ. Data flows one way into Snowflake, nothing flows back into OT. IT/OT boundary preserved." |
| "We tried predictive maintenance — the false alarm rate was too high." | "That's usually a model quality issue, not a platform issue. The Snowpark ML patterns here include calibration steps and per-asset thresholds. We measure false alarms explicitly and the plant engineering lead co-owns the tuning." |
| "How do we monetize this with our OEM partners?" | "Native Apps is the answer. You publish the predictive logic; partners install; your data and their data never mix. Snowflake Marketplace handles the billing surface." |
| "What about data sovereignty across plants in different countries?" | "Snowflake regional accounts. Each plant data stays in its region. Native Apps work across regional accounts with replication." |

## What to bring

- Pre-loaded demo running `make demo-manufacturing`.
- Streamlit dashboard with live asset health view.
- `value-case.md` as leave-behind.
- Access to the plant engineering or maintenance reliability lead.
