# Appendix C – System Screenshots / Interface Designs

All screenshots in this appendix were taken from the running system, not from mock-ups. The script `scripts/capture_screenshots.py` initialises a temporary installation with demonstration users and the demonstration agent (`mirsad init --demo`), starts the gateway with the simulated Najd Trading Co. workspace, and generates activity through the real agent API: eight allowed calls (reading e-mail, looking up customers, listing documents, an internal e-mail and a CRM note update), four calls that the policy denies (a 200-record export, a 250,000 SAR transfer, a request to a cloud metadata address and a tool that does not exist), and four calls that need approval. The approver then approves one request and denies another, leaving two pending. Playwright with Chrome captures the dashboard at 1440 × 900 pixels and the approver app at 390 × 844 pixels (a phone-sized screen). All names, addresses, IBANs and records are fictional.

For the capture run the approval timeout was raised from the default 120 seconds to 15 minutes so that pending requests stay open while the pages are captured. This is why the countdowns show about 14–15 minutes (from a 900-second timeout).

## C.1 Administration Dashboard (English)

![Dashboard sign-in page. The language switch at the top right changes the interface to Arabic before signing in, and the second button selects the colour theme](docs/figures/screens/dash-login.png){#fig:c-dash-login width=6.0}

The Overview page counts the tool calls that were allowed, denied and sent for approval, the requests still waiting, injection detections and sanitised or blocked results; it also shows the gateway overhead per call, the audit-log integrity card with a Verify now button and the decisions over time.

![Dashboard Overview after the seeded activity](docs/figures/screens/dash-overview.png){#fig:c-dash-overview width=6.0}

The Activity and audit log filters events by text, agent, tool, outcome, event type, session, call and time range, verifies the hash chain and exports results as JSON or CSV. Outcome and risk are shown with an icon and a word, not by colour alone.

![Activity and audit log](docs/figures/screens/dash-activity.png){#fig:c-dash-activity width=6.0}

The detail drawer of audit event 38, the approver's denial of a `transfer_funds` request, shows the summary fields, the previous hash and the event hash that link the event into the HMAC chain, the raw event JSON, and filters for all events of the same call or session.

![Detail drawer of an audit event (a denied `transfer_funds` request)](docs/figures/screens/dash-activity-detail.png){#fig:c-dash-activity-detail width=6.0}

![Approvals page. The live pending queue shows each request's risk level, plain-language summary and countdown to expiry with Approve and Deny buttons; the history below records who decided each request and their note](docs/figures/screens/dash-approvals.png){#fig:c-dash-approvals width=6.0}

![Policy editor with the active YAML policy of the demonstration organisation and its version hash. Changes can be compared with the active version, reverted, validated and activated without restarting the gateway](docs/figures/screens/dash-policies.png){#fig:c-dash-policies width=6.0}

![Agents page: the demonstration agent, the policy agent it is mapped to, its key prefix (the full key is shown only once, when it is created or rotated), last-seen time, and rotate, disable and delete actions](docs/figures/screens/dash-agents.png){#fig:c-dash-agents width=6.0}

![Users page with the three roles and what each may do: administrators manage everything, approvers decide on paused actions, and auditors have read-only access to the audit log, policies and tools](docs/figures/screens/dash-users.png){#fig:c-dash-users width=6.0}

![Tools page: the tools discovered from the upstream workspace server and how the active policy profiles each one for the selected agent (allowed, trust of its results, sensitivity, where it sends data, risk and approval mode)](docs/figures/screens/dash-tools.png){#fig:c-dash-tools width=6.0}

The detector playground shows the verdict, the detected language, the model and rule scores, the scan latency, highlighted evidence and obfuscation signals. The model score is 0 because the packaged detector runs in rules-only mode until the model is trained on the team's data.

![Detector playground scanning a benign mixed Arabic–English supplier message](docs/figures/screens/dash-playground.png){#fig:c-dash-playground width=6.0}

The attacker-inbox panel of the Demo console lists everything that left the organisation's domain; in this capture it shows the external supplier reply that the approver approved during seeding, not an attack.

![Demo console: protection switch, scenarios, conversation, tool-call timeline and attacker inbox](docs/figures/screens/dash-demo.png){#fig:c-dash-demo width=6.0}

![Settings page: theme (system, light or dark), language, background notifications for new approvals, account details and server status](docs/figures/screens/dash-settings.png){#fig:c-dash-settings width=6.0}

## C.2 Dashboard in Arabic and in the Dark Theme

![Overview page in Arabic. Labels, key figures and time-range buttons are translated and arranged for right-to-left reading](docs/figures/screens/dash-overview-ar.png){#fig:c-dash-overview-ar width=6.0}

![Activity and audit log in Arabic. The navigation moves to the right and the filters and table columns are mirrored, while tool names, agent identifiers and dates keep their left-to-right form](docs/figures/screens/dash-activity-ar.png){#fig:c-dash-activity-ar width=6.0}

![Policy editor in Arabic. The surrounding interface is right-to-left, while the YAML policy stays left-to-right so that it can be edited and reviewed as code](docs/figures/screens/dash-policies-ar.png){#fig:c-dash-policies-ar width=6.0}

![Overview page in the dark theme, which can follow the operating-system setting or be selected in Settings](docs/figures/screens/dash-overview-dark.png){#fig:c-dash-overview-dark width=6.0}

## C.3 Approver App (English)

![Approver app sign-in on a phone-sized screen. The app is served by the gateway at `/approve` and can be installed to the home screen](docs/figures/screens/pwa-login.png){#fig:c-pwa-login width=2.6}

![Pending requests in the approver app: risk level, tool, requesting agent, the start of the plain-language summary, time since the request and countdown, a prompt to turn on push alerts, and Pending and History tabs](docs/figures/screens/pwa-pending-en.png){#fig:c-pwa-pending-en width=2.6}

![Detail of a critical-risk request to delete a customer record: what the agent wants to do, why Mirsad paused it with the layer behind each reason, and Deny and Approve buttons fixed at the bottom of the screen](docs/figures/screens/pwa-detail-en.png){#fig:c-pwa-detail-en width=2.6}

![Full-length capture of the same request, including the section on where the data came from (here no outside data was linked) and the collapsible list of arguments. The fixed Deny and Approve bar appears in the middle only because of the full-page capture method](docs/figures/screens/pwa-detail-full-en.png){#fig:c-pwa-detail-full-en width=2.6}

## C.4 Approver App (Arabic)

![Pending requests in the Arabic interface. The layout is mirrored, summaries are written in Arabic, and tool names and e-mail addresses keep their original form](docs/figures/screens/pwa-pending-ar.png){#fig:c-pwa-pending-ar width=2.6}

![Detail of the same deletion request in Arabic, with the summary, the reasons for the pause, and the Approve and Deny buttons in right-to-left order](docs/figures/screens/pwa-detail-ar.png){#fig:c-pwa-detail-ar width=2.6}

![Full-length capture of the Arabic request detail, including the data-provenance section and the collapsible arguments; as in the English capture, the fixed button bar appears mid-page because of the capture method](docs/figures/screens/pwa-detail-full-ar.png){#fig:c-pwa-detail-full-ar width=2.6}
