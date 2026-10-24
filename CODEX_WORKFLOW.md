# Codex + Joblane: installed workflow (v0.2)

Joblane now invokes the official Codex CLI using its saved login. On this Mac, the app-local CLI is **0.164.0**, authenticated with ChatGPT. Real analysis, explicit session continuation and public-web discovery have been tested. The global CLI was 0.141.0 and rejected the selected newer model; the app-local installation leaves that global command intact.

## What runs when

```text
./start-joblane
  → private dashboard + persistent queues start
  → wait without model requests
  → manual task OR enabled schedule creates work
  → Codex CLI reads a bounded task and returns structured JSON
  → Joblane validates and stores the result and exact session ID
  → review / CV export / supported form worker
  → result, issue or required input appears in Joblane
```

A CLI process starts per task and exits after the response. Session continuity comes from `codex exec resume SESSION_ID`; the app never uses `--last`. You do not need to keep an interactive Codex terminal open. The Python service must remain running and the computer awake. Initial batches use review mode. No real employer application has been sent during installation.

## Working AI tasks

- **Discovery:** public-web search, original posting inspection, up to six individual listings, paraphrased requirements and saved source/evidence. The source must still be checked for freshness; a publicly visible listing is not proof the employer is hiring today. Duplicate URLs are skipped. Newly discovered jobs can trigger analysis automatically.
- **Analysis:** profile facts against the specific job, fit explanation, tailored English summary/project wording, source fact IDs, gaps and questions. Turkish explanations. No automatic changes to the master profile.
- **Continuation:** each application's exact CLI session is reused, while a fresh profile/job snapshot is authoritative.
- **Issue analysis:** browser field labels and the worker's issue are sent as observations, without passwords, cookies, input values or screenshots. Codex explains the problem; it cannot declare an unconfirmed submission successful.
- **CV export:** use the reviewed suggestions to generate a separate PDF for that application. Old/stale analyses cannot be applied after profile changes; active or possibly submitted jobs cannot be changed.

The master profile has **Answers & skill levels I have confirmed**. Save recurring factual answers there once. The model can translate concrete project work into relevant terminology, distinguish project exposure from professional experience, and reuse confirmed answers. Unconfirmed adjacent skills remain questions. Structural fact-ID checks do not mathematically prove every claim: initial review remains necessary.

## Browser boundary and next implementation

Codex does **not yet drive arbitrary forms**. Python handles a basic single-page adapter with name, email, phone and CV upload. LinkedIn and Kariyer.net direct applications remain handoffs. Unknown questions, choice controls, login, agreements, CAPTCHA and uncertain receipts stop the relevant job. There is no challenge-token extraction or WAF bypass.

The desired next phase is a constrained form action loop: observe the current page → map each question to saved facts/answers → propose allowed field actions → execute → inspect the next page. It needs adapters and live validation on the target platforms. CV rewriting alone does not provide universal application coverage.

Automatic submissions currently require an explicitly authorized exact domain and five reviewed, confirmed real submissions on that domain. After qualification, Codex results with no unanswered questions/review requirement and a strong/possible fit can generate a CV and queue it. The worker still checks the schedule, current form, destination, profile digest and previous submission attempts. Manually recorded receipts do not count.

## Configuration and execution

Install an app-local official CLI with `.venv/bin/python setup-codex.py` (Windows: `.venv\Scripts\python.exe setup-codex.py`). It reuses saved CLI auth or opens the normal `codex login` flow. No authentication token is read, copied or stored by Joblane.

Executable selection: `JOBLANE_CODEX_BIN` → saved binary path → `PATH`.
Model selection: `JOBLANE_CODEX_MODEL` → selected model in `$CODEX_HOME/config.toml` → CLI default. Only the model name is imported from that config. The task process ignores unrelated user configuration and disables shell, plugins, apps, browser/computer control, hooks, memory and subagents; public web search is enabled only for discovery. Read-only sandbox remains enabled.

The prompt goes to stdin, never shell interpolation. JSON schema and output files live under `data/ai/run-N/`. Each task has a four-minute deadline. Errors, cancel and interrupted runs require explicit retry. A second service launch detects an existing Joblane server before touching queues. Task status and concise outputs appear in the dashboard; the subprocess is not an interactive terminal session you need to control.

## Privacy and account usage

The model runs through OpenAI; only the client runs locally. Career facts, job descriptions, saved answers and your task instructions are sent to the model. Top-level contact fields and references are excluded from automatic prompts. Do not put credentials or identity numbers in saved notes.

ChatGPT Plus supports Codex CLI login. Plan limits apply; using an API key instead follows API billing. This integration does not promise unlimited unattended throughput. The Mac test uses the model already selected by the user, `gpt-6-astra`; this can consume allowance faster than lighter models.

A standalone Joblane dashboard avoids using ChatGPT mobile notifications as its control channel. It does not isolate activity from somebody sharing the same OpenAI account. Use a private OS account, private Tailscale access and, if account-level isolation is required, an OpenAI account only you control. Tailscale and private push delivery are not configured by this installation.

## References

- [Codex with your ChatGPT plan](https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan)
- [ChatGPT Work and Codex / Astra CLI minimum version](https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex)
- [Non-interactive execution](https://learn.chatgpt.com/docs/non-interactive-mode)

## v0.4 simplified start

The home screen starts scheduled discovery and analysis after profile confirmation and CLI authentication checks. `auto_prepare` also generates a local tailored PDF after analysis, without sending it. Missing information is marked for attention and triggers the configured notification attempt. Automatic external submission retains the domain qualification rules above. The workspace password must be replaced before live work on the migrated installation.
