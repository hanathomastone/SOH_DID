# SOH_DID Agents Handoff

Last updated: 2026-07-22

## Workspace Rule

- Current confirmed workspace on this PC: `C:\Users\hana0\workspace\SOH_DID`
- Other PCs may clone or open the repository in a different folder. Always treat the Git repository root as the working base, not this absolute path.
- Before any future work, confirm the current directory with `Get-Location` or equivalent and check Git state with `git status --short --branch`.
- Always read and update this file when project status, TODOs, assumptions, or handoff notes change.
- For each meaningful update, commit and push the update to Git so another PC can continue from the remote branch.

## Git / Remote

- Current branch checked on 2026-07-16: `main`
- Remote checked on 2026-07-16: `origin` -> `https://github.com/hanathomastone/SOH_DID.git`
- Git may report dubious ownership in Codex sandbox because the repository owner differs from the sandbox user. Use a per-command safe directory option if needed:
  - `git -c safe.directory=C:/Users/hana0/workspace/SOH_DID status --short --branch`
- Do not rely on the exact safe-directory path on another PC. Replace it with that PC's repository path if Git requires it.

## Project Summary

- Flask app under `main/`.
- Main entry point: `main/run.py`.
- Requirements: `main/requirements.txt`.
- API route modules:
  - DID routes: `main/myapp/routes/did.py`
  - Token routes: `main/myapp/routes/token.py`
  - Common DChain proxy routes: `main/myapp/routes/common.py`
- Shared DChain and environment configuration: `main/myapp/utils.py`.
- MySQL helper modules are under `main/myapp/*_db*.py` and `main/myapp/mysql_db.py`.
- EC2 deployment examples are under `main/deploy/ec2/`.

## Work Completed So Far

Recent Git history shows these completed changes:

- Replaced DID routes with a local DID implementation.
- Added `did:key` generation using Ed25519 keys.
- Added local DID document/private key persistence under configurable data directories.
- Added DID signup flow that creates a wallet account during DID creation.
- Added JSON error handling for DID creation failures.
- Reconnected MySQL before database operations.
- Added configurable log directory behavior and API response display changes.
- Updated token support so token creation stores local contract metadata and token transfer can update user token balances.
- Updated `utils.py` configuration defaults.
- Changed default and EC2 example `DCHAIN_BASE_URL` from the old private/internal URL to `https://www.daegu.go.kr/daeguchain/v2/mitum`.
- Added structured DChain timeout/connection error responses, a configurable `DCHAIN_TIMEOUT`, and `/common/dchain_config` to confirm the effective upstream settings on deployed servers.
- Set DChain chain name defaults/examples to `minic`, matching `did:mitum:minic:*` owner DIDs and avoiding DChain `B0701` invalid chain errors.
- Added `created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP` to the local MySQL `DID` and `user` tables so new rows record creation time automatically.

Current status at the time this file was created:

- Working tree was clean before adding this handoff file.
- Branch was `main`.
- Local branch appeared aligned with `origin/main`.
- No previous `agents.md` or `AGENTS.md` file existed.

## Important Notes

- `main/myapp/utils.py` currently contains hardcoded default service URLs, API tokens, owner keys, and MySQL credentials. Treat those values as sensitive. Prefer environment variables for real deployments and avoid copying secrets into docs or logs.
- `main/README.md` appears to contain broken Korean text encoding. Restore or rewrite it before relying on it as project documentation.
- `main/logs/app.log` is tracked in the repository. Consider whether runtime logs should move to `.gitignore`.
- The DID implementation currently writes generated DID data and private keys to local disk. Confirm `DID_DATA_DIR` or `DATA_DIR` in each environment before testing or deploying.
- DChain and MySQL integration tests may require network access and real credentials.
- DID generation is local to this app, but wallet creation, token creation, token transfer, token list, and other chain functions go through Daegu Chain using `DCHAIN_BASE_URL`.
- If token list/history lookup still fails after deployment, call `/common/dchain_config` on the running server first to confirm the effective `DCHAIN_BASE_URL`; environment variables can override code defaults. On EC2, systemd reads this from `/etc/soh-did/soh-did.env`.

## TODO

- [ ] Move sensitive defaults from `main/myapp/utils.py` to a safe `.env` or deployment environment setup, then rotate any exposed credentials if they are real.
- [ ] Add or update `.gitignore` for runtime files such as logs, local DID data, Python caches, virtual environments, and local environment files.
- [ ] Restore or rewrite `main/README.md` with correct Korean encoding and current setup instructions.
- [ ] Document local setup: Python version, virtual environment creation, `pip install -r main/requirements.txt`, required environment variables, and run command.
- [ ] Add smoke-test instructions for DID create/signup, DID lookup, token create, token transfer, and common DChain proxy endpoints.
- [ ] Add automated tests for local DID generation/persistence that do not require external DChain or MySQL access.
- [ ] Add tests or mocked checks for token route request shaping and local DB update behavior.
- [ ] Verify EC2 deployment files in `main/deploy/ec2/` still match current environment variables and run command.
- [ ] Decide whether local DID private key storage needs encryption or stricter file-permission handling for the deployment target.
- [ ] Before each handoff, update this file with the latest completed work, open issues, verification performed, and Git commit pushed.

## Next-Agent Checklist

1. Confirm repository root on the current PC.
2. Read this `agents.md`.
3. Run `git status --short --branch`.
4. Pull the latest `origin/main` if appropriate.
5. Inspect any uncommitted user changes before editing.
6. Make the requested code/doc changes.
7. Update this `agents.md` if project state or TODOs changed.
8. Run the relevant tests or smoke checks that are feasible in the current environment.
9. Commit and push the completed update.
