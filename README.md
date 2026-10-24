# Joblane · v0.4

Private personal job-search workspace. Python manages local storage, scheduling and supported browser forms; Codex handles public job discovery, analysis, tailored wording and email drafts.

The complete Turkish setup and usage instructions are in [KULLANIM.md](KULLANIM.md).

## Run on this Mac

```sh
./start-joblane
```

Open http://127.0.0.1:8765/ while the service runs. Do not open `index.html` as the app. The launcher loads optional `config.local.sh`; use `config.example.sh` as its starting point. Keep the terminal running. `caffeinate -i ./start-joblane` can prevent idle sleep for that session.

## Start using it

1. Set your private workspace password in Schedule & settings.
2. Review your master CV facts, links and recurring answers. PDF import extracts text for you to review; it does not populate structured profile fields automatically.
3. Check the saved Codex CLI connection. Connect Outlook for email; configure Tailscale and Telegram for phone access and notifications.
4. Confirm your profile on the home screen and start automation. Scheduled discovery and CV preparation use the saved execution window. There is no activity before you enable it.

Empty applications/history screens explain the next step. No local practice form or demo-creation endpoint is shipped. Development tests run in temporary storage.

## Capabilities and limits

- Public discovery requests up to six source-backed listings per search, with URL deduplication. Completeness and freshness need verification.
- Automatic analysis generates separate tailored CV PDFs. Source-backed suggestions do not replace the master profile. Missing information is raised for attention.
- Browser filling supports recognized name, email, phone and CV controls on basic single-page company forms. Unknown questions, login, challenges and unsupported controls pause.
- First submissions are reviewed. Automatic sending requires an explicitly authorized exact company domain with five reviewed, confirmed real submissions. This is not universal unattended coverage.
- LinkedIn and Kariyer.net direct submissions remain manual handoffs. Employer application URLs can use the supported form adapter.
- Outlook uses Microsoft Graph delegated Mail.Send and a native credential store. Drafts include recipient, subject, body and an immutable PDF attachment. Sending requires review. Inbox reading and automatic email sending are not implemented.
- History preserves exact PDF versions, email drafts, delivery state and integrity hashes. Uncertain results never retry automatically.
- Pushover reports missing answers, AI failures and browser blockers; routine discovery/preparation does not emit progress notifications. A notification test is available in settings. Exact device validation precedes sending; use a private account with only your own devices.
- Tailscale Serve offers private phone access, but does not run the Python service or provide remote desktop.

## New installations

Python 3.12+ is required. macOS/Linux: `./start-macos-linux.sh`. Windows: install Python, run `setup-windows.cmd`, then `start-windows.cmd`. On Windows optional local settings are in `config.local.ps1`; on Mac they are in `config.local.sh`.

Install Node.js, then run `setup-codex.py` with the app's virtualenv Python to install the app-local CLI and complete official sign-in. See [CODEX_WORKFLOW.md](CODEX_WORKFLOW.md).

For Outlook run the virtualenv Python with `-m pip install -r requirements-outlook.txt`, then `connect-outlook.py`. Register your own public desktop app first, as described in the Turkish guide. No client secret is used.

## Data

`data/` holds private profile facts, the database, artifacts and browser state. Keep it and `config.local.*` private. Stop the service before backups. Existing artifact paths are absolute: migrating an existing workspace to a new path or operating system requires path migration, not just copying files. Reconnect Outlook on the new machine.

## Development

```sh
.venv/bin/python -m pip install pytest
.venv/bin/python -m pytest -q
```

Tests use temporary databases and mocked external services. Real employer submissions, Outlook authorization and phone notification delivery are not performed by tests. Current validation is described in [VALIDATION.md](VALIDATION.md).

## Telegram notifications

Create a dedicated bot with official @BotFather, then run `.venv/bin/python connect-telegram.py`. Install `requirements-telegram.txt` if needed. A short-lived start link pairs exactly one private chat; the token stays in the native OS keyring. Refresh the dashboard and use the notification test button. Telegram takes precedence over optional Pushover without automatic fallback. Alerts contain no application details and are notifications only, not a remote command channel. Real Telegram setup and phone delivery require the user’s bot and account.
