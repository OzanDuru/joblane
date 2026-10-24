# Joblane v0.4 validation

Validated 24 October 2026 on the current Mac.

## Automated checks

61 tests passed with `.venv/bin/python -m pytest -q`. Coverage includes session/authentication protection, password change and revocation of other sessions, required password transition, automation start confirmation and CLI readiness, scheduling, URL validation, form authorization, immutable CV/email archives, uncertainty handling, source-linked AI results, automatic local PDF preparation, first-application attention, and exact push-device validation. External browser actions, Microsoft Graph and push requests use test doubles; no employer was contacted.

JavaScript syntax checks passed for changed app, home and history files; shell syntax check passed for the Mac launcher.

## Active workspace cleanup

Verified zero rows in jobs, events, ai_runs, ai_sessions, cv_versions, deliveries and notifications. Job-specific config and generated artifacts were removed. Main profile and authentication were retained. Scheduling is off. Old exports and pre-cleanup data are backed up outside the active app under `../../work/joblane-backups/`.

Practice creation and local practice form routes return 404 when authenticated. The browser adapter no longer allows the former local practice navigation exception.

## Browser verification

Opened the running local service in the in-app browser. Verified the home screen with zero counters, disabled start until the setup password is replaced, ChatGPT CLI status, empty Applications and History screens, visible password-change controls and disabled notification test before configuration. No browser errors/warnings were recorded. The new primary screenshot is `../joblane-clean-start.png`.

## Remaining user setup and unverified integrations

Outlook OAuth consent, real email sending, Tailscale phone access and Pushover delivery to the real phone are not yet completed. The user must choose a private workspace password. Current source checks do not establish universal automatic submission: LinkedIn/Kariyer.net and unsupported forms still hand off; email sending requires review. PDF upload extracts text for manual profile review. The service does not autostart at Mac boot.

## Telegram extension

69 tests pass after Telegram support. Added checks for nonce/date/private-sender pairing, ambiguous pairing rejection, keyring-only token storage, private-target verification before send, generic message contents, notification failure reporting and redacted API errors without retries. The running HTTPS service serves the updated notification UI. No real Telegram account is paired yet and no Telegram message was sent during validation. BotFather creation and actual phone delivery remain user setup steps.

### 2026-10-25 — Operational journal, cancellation, shared UI and sessions

- Added an allowlisted, incremental CLI-event journal with exact emitted search queries, source titles/URLs, outcome stages and source-time uncertainty for old logs. Raw reasoning, arbitrary agent output, snippets and credentials are excluded. Existing cancelled task enriched without rerunning it.
- Cancellation no longer sends an attention notification. Genuine failures retain notification behavior. Separate global pause/resume and per-task cancellation controls, tested through API and isolated browser UI.
- Shared spacing/color system, Turkish navigation/primary forms, persisted explicit light/dark/system preference. Confirmed theme survives reload and pause/resume buttons change in both directions.
- Added allowlisted LinkedIn/Kariyer login-window setup using the existing persistent application browser. This is session preparation, not a completed platform submission adapter.
- Full Python suite: 76 passed before final journal enrichment. Targeted journal/CLI/session suite after enrichment: 20 passed. Home-state JavaScript checks passed. Production HTTPS assets return 200.
- Browser and fixture checks used an isolated temporary database; no employer submissions or real Telegram test messages were sent.

### 2026-10-25 — Login page stuck on spinner

- Fixed the idle/paused worker starving synchronous Playwright route callbacks. The worker now pumps browser events between bounded queue polls, keeping user-operated login/MFA/review tabs responsive while preserving public-network request guards.
- Browser closure resets runtime/context/page references so the next login can reopen the persistent profile.
- `tests/test_site_sessions.py`: 5 passed, including idle/paused dispatch and closed-context recovery.
- Restarted the inactive production service, reopened LinkedIn through the authenticated Joblane settings UI, and verified the actual LinkedIn email/password form became visible. No credentials entered and no login submitted by the agent.

### 2026-10-25 — Actual session verification

- Replaced user-declared confirmation with a worker-thread verification job. Refreshes the account page, detects login/challenge states and checks authenticated account UI; LinkedIn additionally requires its local session cookie. Cookie values never enter dashboard responses or application logs.
- Added verification badge, session-presence indicator, check time and recheck action. Restart invalidates the live badge while preserving the last verified time.
- Added graceful worker shutdown joins to allow persistent-browser cleanup.
- Seven targeted session tests passed, including cookie-without-account-UI rejection and credential-free API metadata. Verified the real saved LinkedIn session through production Tailscale UI: verified, session present. No job applications submitted.

### Kariyer.net session evidence and browser compatibility (2026-10-25)
- Removed the misleading generic cookie-presence indicator from session cards. Kariyer.net never treats HttpOnly/challenge cookies as authentication evidence; old persisted presence claims are cleared on startup.
- Kariyer.net requires a visible authenticated control after a page refresh; hidden logout controls do not count. Unknown session-cookie evidence stays null.
- Kariyer.net now opens installed stable Google Chrome using a separate persistent profile (`browser-profile-kariyer-chrome`). No custom user-agent, cookie copying or challenge bypass was added. LinkedIn keeps its existing profile; contexts share the worker's Playwright runtime and are pumped/closed independently.
- Validation: 87 pytest tests passed; JavaScript home/status checks passed. Live Tailscale panel no longer displays the false cookie claim. Clicking Kariyer.net login reached “Doğrulama bekliyor” using the new Chrome launch path. Successful user sign-in and challenge completion are not yet verified.

### Rejected CAPTCHA handling (2026-10-25)
- Recognize “Captcha Forbidden” (including visible error 60500) as a blocked verification, without claiming a valid session or exposing the diagnostic identifier.
- Check for a current challenge/error before reloading the login page, preserving the error and avoiding restarting a rejected CAPTCHA when the user requests an account check.
- Targeted validation: 14 site-session tests passed, including a regression that fails on any reload of a page displaying Captcha Forbidden.
- This improves detection and reporting; the external CAPTCHA rejection is not resolved or bypassed. An already signed-in normal Chrome profile is not equivalent to a fresh login challenge.

### Kariyer.net human login before controlled verification (2026-10-25)
- User confirmed a fresh login succeeds in normal Chrome incognito, while Joblane's automated browser returns 60500. This narrows the issue to the browser/profile path; it does not establish a specific detection mechanism.
- Kariyer login button now launches installed Chrome directly with a dedicated `browser-profile-kariyer-native` profile, without Playwright/debugger/UA overrides. The regular user profile and older Joblane profiles are left intact.
- Account verification waits for the human Chrome to exit, then opens that same dedicated profile under Playwright and checks the account UI. Chrome's PID lock is respected across Joblane restarts; no lock/cookie deletion, session copying, or CAPTCHA solving is performed.
- 17 targeted tests and JS state checks passed, covering native launch arguments, no automated launch on the login command, duplicate launch prevention, busy profile handling, and persistent lock handling. A successful real login and its later automated verification still require the user's sign-in.

### Native Chrome cookie encryption compatibility (2026-10-25)
- Installed Playwright 1.64.1 adds `--use-mock-keychain` and `--password-store=basic` by default. These differ from the native Chrome launch and can prevent reading encrypted cookies from its existing profile.
- Kariyer.net's controlled Chrome now excludes only those two test credential-store overrides and resolves the exact same profile path as the manual launch. User-agent, security checks and routing restrictions are unchanged. No cookie extraction, copying, decryption in Python, or token disclosure was added.
- All 17 site-session tests passed, including launch configuration regression checks. This verifies configuration; real authentication remains subject to the site and the existing session's validity.

### Controlled test through the user's existing Chrome session (2026-10-25)
- Inspected the user's existing Kariyer.net `/hesabim` tab through the Chrome connector: account UI and CV section were visible. This confirms only that Chrome session, not Joblane's separate worker profile. No cookies were exported or copied, and no worker authentication status was forced to verified.
- Opened Assessment Systems PHP Developer listing: 5+ years PHP/Laravel required, so no application was initiated. Following the Junior QA & Data Specialist suggestion reached a press-and-hold human verification in the same authenticated normal Chrome browser.
- No application was submitted, no employer received CV/contact data through an application, and the verification remains for user completion. Evidence: ../joblane-kariyer-application-blocker.png.
- CAPTCHA detection now also inspects bounded iframe body text because provider errors need not appear in the top-level DOM. 18 targeted tests passed, including an iframe 60500 regression.

### Native desktop interaction comparison (2026-10-25)
- With the user temporarily leaving Chrome idle, used only macOS Chrome window accessibility/input controls (no tab CDP/DOM tools for this navigation).
- Searched `junior`, opened the same Pologron Junior QA & Data Specialist listing (4576135) that previously presented human verification, and opened `/basvuru-tamamlama/4576135`. The authenticated form loaded without a challenge during this trial. This is an observation, not proof of the vendor's detection mechanism or reliability across future runs.
- Form reached final review: existing Kariyer CV “Ozan Duru Özgeçmiş” (last updated 21.10.2026), no cover letter selected for the test, site-prefilled monthly net expectation 50,000 TRY, company-follow option unchecked. No final submission click was made. No CV was edited for this test.
- Evidence: ../joblane-kariyer-native-review.png. Native desktop control here is supplied by the current assistant's computer-use tools; it has NOT been implemented as an unattended Joblane worker driver. Do not label the worker connected/verified based on this separate Chrome session.
