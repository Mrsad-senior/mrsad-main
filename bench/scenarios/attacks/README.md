# Attack files (supplied by the human team)

This folder is intentionally empty. The development team does not author attack content: injection
tasks and attack templates are written, reviewed and added here by the human research team only.

## What goes here

One or more `*.yaml` files, each starting with `version: 1` and containing only these two lists.
They are validated against `../schema.json` by `python -m bench.loader`.

### `injection_tasks`

The *goal* an attacker would want the agent to carry out, expressed as tool actions and a success
predicate on World side effects. Fields:

| Field | Meaning |
|---|---|
| `id` | unique slug |
| `category` | one of `exfiltration`, `destruction`, `fraud`, `phishing`, `privilege` |
| `goal` | short neutral description of the goal (used to fill the `{goal}` placeholder) |
| `actions` | list of `{tool, args}` steps; checked against the demo tool schemas |
| `success` | predicate on World side effects (same operators as user tasks, e.g. `sent_to_domain`, `deleted`, `transfer_to`, `fetched_domain`) |

Destination values must use the reserved `.example` TLD (for example the attacker domains listed in
`docs/dev/BUILD_SPEC.md`) and fictional IBANs/ids only.

### `attack_templates`

| Field | Meaning |
|---|---|
| `id` | unique slug |
| `lang` | `en`, `ar` or `mixed` |
| `variety` | optional: `en`, `msa`, `gulf`, `egyptian`, `levantine`, `arabizi`, `mixed` |
| `style` | one of `ignore_previous`, `important_instructions`, `system_impersonation`, `tool_knowledge`, `completion`, `social_engineering`, `obfuscated`, `dialect` |
| `template` | the text; must contain a `{goal}` and/or `{actions_text}` placeholder |
| `source` | provenance (paper / dataset and licence) |

The full field list, including the optional fields added for attack execution, is the
`injectionTask` / `attackTemplate` definitions in `../schema.json`.

## How these files are used

The loader validates them and reports how many are available. Once both lists are present, attack
episodes are executed by `bench/attacks.py` and the runner; how they are built, run and reported is
described in `docs/benchmark.md`.
