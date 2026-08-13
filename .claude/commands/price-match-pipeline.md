---
description: Run the full Researcher → Solution Designer → Prototyper pipeline for a customer price-match request.
argument-hint: [product] [customer_price] [zipcode]
---

Run the three-stage Price Match Assistant pipeline end to end for:

- Product: $1
- Customer price: $2
- ZIP code: $3 (default to 10001 if not provided)

Do not skip stages, do not merge stages, and do not summarize a stage before it has actually run. Execute strictly in order:

## Stage 1 — Researcher
Invoke the `researcher` subagent with the product, customer price, and ZIP code above.
Capture its full structured brief verbatim (product, customer price, Target API listings, Google Sheet comparison, price range, verdict, recommendation, confidence/gaps).
If the researcher cannot find enough data, stop and report that the pipeline halted at Stage 1, including what is missing. Do not fabricate findings to continue.

## Stage 2 — Solution Designer
Invoke the `solution-designer` subagent, passing it the Stage 1 output verbatim as "Researcher Findings". Do not paraphrase or drop fields from Stage 1 before handing it off.
Capture the full output: opportunity framing, the 3 concepts with scores, the recommended solution, the experience specification, MVP definition, implementation contract, measurement/risks, and next validation steps.
If Stage 1's evidence is too thin for a confident recommendation, the solution designer should say so explicitly rather than inventing certainty; continue to Stage 3 only with the concept it actually recommends.

## Stage 3 — Prototyper
Invoke the `prototyper` subagent, passing it the Stage 2 "Recommended Solution", "Experience Specification", "MVP Definition", and "Implementation Contract" sections verbatim.
Instruct it to build the smallest working slice into the existing app (`app.py`, `templates/index.html`, `static/app.js`, `static/styles.css`), reusing the existing `/api/verify-price` contract rather than inventing a new one.
Capture its full output: slice built, files changed, verification performed, and MVP coverage/deferred items.

## Final report
After all three stages complete, report back with:

1. A one-paragraph summary of the customer scenario and the verdict reached.
2. The recommended concept name and why it was chosen.
3. The files the prototyper actually changed (verified via `git status`, not just claimed).
4. Any stage that had to make an assumption due to missing data, listed explicitly.
5. What remains out of scope / deferred, per the prototyper's MVP coverage section.

Do not mark a stage complete unless its subagent actually returned output. Do not commit or push changes unless explicitly asked.
