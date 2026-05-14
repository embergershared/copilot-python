# Work Routing

How to decide who handles what.

## Routing Table

| Work Type | Route To | Examples |
|-----------|----------|----------|
| Architecture, scope, module boundaries | Ripley | "design the X module", "should this be one service or two?" |
| Code review, reviewer gates | Ripley | PR review, approve/reject design proposals |
| Issue triage (`squad` label) | Ripley | Read issue, assign `squad:{member}` label |
| Python application code | Bishop | "implement /endpoint", "refactor settings", "type the public API" |
| Reusable modules / packaging | Bishop | "extract logging into a shared module", "add to pyproject" |
| Telemetry, logging, OpenTelemetry SDK | Bishop (with Parker for sinks) | "add structured JSON logs", "wire OTel exporter" |
| Docker, GitHub Actions, CI/CD | Parker | "fix the build", "add a workflow", "harden the Dockerfile" |
| Azure infra, OIDC, managed identity | Parker | "deploy to Container Apps", "wire App Insights" |
| Seq / external log sinks / observability backends | Parker | "ship logs to Seq", "configure CLEF batching" |
| Secret hygiene, .env, container security | Parker | "review for secret leaks", "harden the runtime" |
| Test plans, pytest, edge cases | Hudson | "write tests for X", "what's the coverage gap?" |
| Integration tests for FastAPI routes | Hudson | "test the /health endpoint end-to-end" |
| Session logging, decisions merging | Scribe | Automatic — never needs routing |
| Work monitoring, backlog, GitHub issues | Ralph | "Ralph, go", "what's on the board?" |

## Issue Routing

| Label | Action | Who |
|-------|--------|-----|
| `squad` | Triage: analyze issue, assign `squad:{member}` label | Ripley |
| `squad:ripley` | Architecture, design, review work | Ripley |
| `squad:bishop` | Python implementation work | Bishop |
| `squad:parker` | Infra, CI, telemetry sink work | Parker |
| `squad:hudson` | Test work | Hudson |

### How Issue Assignment Works

1. When a GitHub issue gets the `squad` label, **Ripley** triages it — analyzing content, assigning the right `squad:{member}` label, and commenting with triage notes.
2. When a `squad:{member}` label is applied, that member picks up the issue in their next session.
3. Members can reassign by removing their label and adding another member's label.
4. The `squad` label is the "inbox" — untriaged issues waiting for Ripley.

## Rules

1. **Eager by default** — spawn all agents who could usefully start work, including anticipatory downstream work (Hudson can write tests from the spec while Bishop builds).
2. **Scribe always runs** after substantial work, always as `mode: "background"`. Never blocks.
3. **Quick facts → coordinator answers directly.** Don't spawn an agent for "what port does the server run on?"
4. **When two agents could handle it**, pick the one whose domain is the primary concern. (e.g., logging *code* → Bishop; logging *sink wiring* → Parker.)
5. **"Team, ..." → fan-out.** Spawn all relevant agents in parallel as `mode: "background"`.
6. **Anticipate downstream work.** If Bishop is building a module, spawn Hudson to draft the test plan from requirements simultaneously.
7. **Issue-labeled work** — when a `squad:{member}` label is applied to an issue, route to that member. Ripley handles all `squad` (base label) triage.
