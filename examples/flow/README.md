# Flow Example — Scheduled Agent Sessions

Flows let you schedule agent sessions to run on a cron expression. The full reference (frontmatter fields, conditional execution via shell scripts, template variables) lives in the [Flows section of the root README](../../README.md#flows---scheduled-agent-sessions).

## Files

- [`morning-trivia.md`](morning-trivia.md) — minimal flow: every day at 7:30 AM, ask the `developer` agent a trivia question.

```yaml
---
name: morning-trivia
schedule: "30 7 * * *"   # standard cron
agent_profile: developer  # any installed profile
---

What is the capital of France?
```

The body is the prompt the agent will receive when the schedule fires.

## Setup

```bash
# 1. Start the CAO server (must be running for the schedule to fire)
cao-server

# 2. Install the agent the flow uses
cao install developer

# 3. Add the flow
cao flow add examples/flow/morning-trivia.md
```

## Common commands

```bash
cao flow list                   # show all flows + next run time + enabled status
cao flow run morning-trivia     # fire it now (ignores schedule)
cao flow disable morning-trivia # pause without removing
cao flow enable morning-trivia
cao flow remove morning-trivia
```

## See also

- [README → Flows - Scheduled Agent Sessions](../../README.md#flows---scheduled-agent-sessions) — frontmatter reference, conditional `script:` field, and template variables for dynamic prompts.
