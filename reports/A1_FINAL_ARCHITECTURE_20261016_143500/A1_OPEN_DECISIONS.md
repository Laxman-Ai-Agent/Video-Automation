# A1 Open Decisions — Specific Parameters for Human Selection

**Audit ID:** A1-DEC-01  
**Timestamp:** 2026-10-16T14:40:00+05:30  
**Repository Root:** `E:\audio-to-video`  

---

The major architectural decisions (PIN requirement, tripartite agent classification, no physical folder moves, and gradual execution engine convergence) have been formally resolved in this report package based on user directives.

The following minor implementation parameters remain open for your preference before beginning Phase A2:

### 1. Laxman PIN Secret Format & Storage Preference
- **Resolved:** A PIN is strictly required for protected actions; no plaintext secrets in Git.
- **Decision Needed for Phase A2:**
  - **Option A (Numeric PIN via Environment / Setup):** A 4-to-8 digit numeric PIN (e.g. `849201`) stored as an environment variable `LAXMAN_APPROVAL_PIN` or initialized via a local interactive CLI script (`python scripts/set_laxman_pin.py`) storing a salted hash.
  - **Option B (Alphanumeric Passphrase):** An arbitrary passphrase / token (e.g. `Laxman-Production-Key-2026!`).
  - *Recommendation:* Option A (Numeric PIN or short passphrase) is easiest for interactive browser use on the `/approvals` screen while providing complete security against accidental clicks or automated agent bypass.

### 2. Timing of `dashboard/` Directory Cleanup
- **Resolved:** `dashboard/` is 175 MB of untracked, obsolete node modules from before the UI reset. It is confirmed safe to remove.
- **Decision Needed:**
  - **Option A (Immediate Cleanup in A2):** Reclaim the 175 MB of disk space immediately at the beginning of Phase A2 after taking a local backup.
  - **Option B (Deferred Cleanup in A7):** Wait until the final Phase A7 production hardening milestone to perform all cleanup actions together.
  - *Recommendation:* Option A cleans up the filesystem clutter right away, but Option B follows strict phase sequencing.

### 3. External GitHub Connector Credentials (Phase A5)
- **Resolved:** Skill discovery will search internal skills first; external candidates will be quarantined.
- **Decision Needed for Phase A5:**
  - When querying the public GitHub API for skill repositories, unauthenticated calls are rate-limited to 60 requests/hour.
  - Would you like the option to provide an optional `GITHUB_TOKEN` in `.env` for higher rate limits during skill discovery, or should the agent operate strictly under unauthenticated public rate limits?
