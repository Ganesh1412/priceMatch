---
description: Run the full Researcher → Solution Designer → Prototyper → Communicator → Manager pipeline for a customer price-match request.
argument-hint: [product] [customer_price] [zipcode]
---

Run the five-stage Price Match Assistant pipeline end to end for:

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

## Stage 4 — Communicator
Invoke the `communicator` subagent after the prototyper completes, passing it the full verified outputs from Stages 1 through 3. Include the research evidence and limitations, the recommended solution and target user, and the prototyper's actual files changed, verification, MVP coverage, deferred items, and assumptions.
Ask it to produce an evidence-grounded messaging system, marketing materials, campaign concepts, and a practical go-to-market strategy. It must distinguish shipped capabilities from future ideas and must not invent customer outcomes, testimonials, market data, or performance claims.
Capture the full output using the communicator's output format.

If the prototyper did not produce a working slice or its verification is missing, the communicator may still create a provisional narrative, but it must label claims as assumptions and state what must be validated before launch.

## Stage 5 — Manager
Invoke the `manager` subagent after the communicator completes. Pass it the full, unabridged outputs from Stages 1 through 4, plus any available repository state or test evidence.
Ask it to review strategic alignment across research, design, implementation, and messaging; make an explicit readiness decision; identify conflicts and material risks; and produce an executive summary with a prioritized operational plan. It must distinguish shipped and verified behavior from deferred work, assumptions, and unmeasured outcomes.
Capture the full output using the manager's output format. Do not let the manager override evidence with a launch recommendation: it may recommend only proceed, proceed with conditions, hold for validation, or stop and re-scope.

## Final report
After all five stages complete, report back with:

1. A one-paragraph summary of the customer scenario and the verdict reached.
2. The recommended concept name and why it was chosen.
3. The files the prototyper actually changed (verified via `git status`, not just claimed).
4. Any stage that had to make an assumption due to missing data, listed explicitly.
5. What remains out of scope / deferred, per the prototyper's MVP coverage section.
6. The communicator's core positioning idea, strongest launch message, campaign recommendation, and evidence gaps.
7. The manager's readiness decision, top risks, accountable next actions, and decision gate.

Do not mark a stage complete unless its subagent actually returned output. Do not commit or push changes unless explicitly asked.
