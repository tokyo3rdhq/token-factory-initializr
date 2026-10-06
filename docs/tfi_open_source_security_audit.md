# TFI Open Source Security Audit

You are performing a security audit of the public repository:

https://github.com/tokyo3rdhq/token-factory-initializr

## Context

Token Factory Initializr (TFI) is an open-source project under the MAGI ecosystem.

The repository is public and contains both the Web application and the model data pipeline.

GitHub Actions workflows are intentionally split into three responsibilities:

```text
.github/workflows/
├── web-ci.yml
├── data-ci.yml
└── fetch-models.yml
```

Their intended responsibilities are:

* `web-ci.yml`

  * Web application CI
  * Build, lint, test, type-check, etc.
  * MUST NOT require production secrets.

* `data-ci.yml`

  * Data-side CI
  * Test data schemas, fetchers, processors, pipeline logic, etc.
  * MUST NOT require production secrets.
  * MUST be safe to execute against pull requests and fork contributions.

* `fetch-models.yml`

  * Production model-data refresh pipeline.
  * Fetches model data from external sources.
  * Processes, validates, reconciles and publishes model data.
  * May require Cloudflare credentials to write production data to Cloudflare KV.
  * This workflow is the primary production trust boundary.

The project is intentionally open source.

The existence of GitHub Repository / Environment Secrets is NOT considered a security problem by itself. The goal is to ensure that untrusted code cannot gain access to production credentials.

---

# 1. Audit Objectives

Perform a security audit focused on:

1. GitHub Actions security
2. Public repository / fork security
3. Production secret isolation
4. Cloudflare credential security
5. Data pipeline supply-chain security
6. External data ingestion security
7. Web/API security
8. Generated configuration security
9. Dependency and CI supply-chain security
10. Open-source project security posture

Do NOT perform a broad theoretical security review unrelated to the actual repository.

Prioritize realistic attack paths that could affect:

* GitHub Actions
* Cloudflare KV
* Cloudflare Pages
* production model catalog
* generated configuration artifacts
* repository integrity
* production credentials

---

# 2. Audit Rules

## 2.1 Inspect Before Changing

First inspect the repository.

At minimum inspect:

```text
.github/workflows/web-ci.yml
.github/workflows/data-ci.yml
.github/workflows/fetch-models.yml

SECURITY.md
CONTRIBUTING.md
CODE_OF_CONDUCT.md
README.md

package.json
package-lock.json / pnpm-lock.yaml / yarn.lock

pyproject.toml
requirements*.txt
data/
web/
functions/
shared/
```

Also inspect:

* `.gitignore`
* `.dockerignore` if present
* environment examples
* scripts invoked by workflows
* Cloudflare configuration
* Wrangler configuration
* test fixtures
* shell scripts
* workflow actions
* any deployment configuration

Do not assume the README accurately describes the implementation. Compare documentation against actual workflow behavior.

---

# 3. Threat Model

Treat the following actors as untrusted:

### Attacker A — External Fork Contributor

An attacker can:

* fork the repository
* modify source files
* modify tests
* modify build scripts
* modify Python code
* modify package scripts
* submit a pull request

Assume the attacker can control any code executed from their PR.

The attacker must NOT be able to obtain:

```text
CLOUDFLARE_API_TOKEN
CLOUDFLARE_ACCOUNT_ID
CLOUDFLARE_KV_NAMESPACE_ID
```

or any other production credential.

---

### Attacker B — Malicious Dependency / Supply Chain

Assume:

* npm dependency could be compromised
* PyPI dependency could be compromised
* transitive dependency could be compromised
* GitHub Action could be compromised

Determine whether such code could execute with production credentials.

---

### Attacker C — Malicious Upstream Model Data

Model metadata comes from external sources such as:

* NVIDIA
* AMD
* Hugging Face
* OpenRouter
* other configured model sources

Treat external model metadata as untrusted input.

Check whether malicious content can:

* inject HTML
* inject JavaScript
* poison generated configuration
* manipulate model identifiers
* manipulate provider metadata
* cause excessive resource consumption
* trigger unsafe shell execution
* alter Cloudflare KV state unexpectedly

---

# 4. Workflow Security Audit

Perform a detailed audit of all three workflows.

## 4.1 web-ci.yml

Verify:

* triggers
* permissions
* checkout behavior
* dependency installation
* build scripts
* test scripts
* shell execution
* third-party actions
* artifact handling
* cache handling
* secret usage

Expected security property:

```text
PR / fork
    ↓
web-ci.yml
    ↓
build/test
    ↓
NO production secrets
```

Flag any production secret access as at least HIGH risk unless there is a compelling and documented reason.

Recommend:

```yaml
permissions:
  contents: read
```

or an even narrower permission set where possible.

---

# 5. data-ci.yml

This workflow is especially important because it executes data-side Python code.

Verify that:

```text
fork PR
   ↓
data-ci.yml
   ↓
Python code
   ↓
NO production credentials
```

Audit for:

* arbitrary Python execution
* `subprocess`
* `os.system`
* `shell=True`
* dynamically generated shell commands
* untrusted model IDs inserted into commands
* environment-variable interpolation
* test fixtures containing secrets
* dynamically downloaded code
* `pip install` behavior
* unpinned dependencies
* GitHub Action versions
* artifact poisoning
* cache poisoning

Determine whether an attacker can modify:

```text
pyproject.toml
requirements.txt
package scripts
Makefile
scripts/
data/
tests/
```

and cause arbitrary code execution.

If yes, determine whether the workflow has access to secrets.

The critical condition is:

```text
Attacker-controlled code
+
Production secret
=
potential credential compromise
```

If the workflow has no production secrets, explicitly mark this as an acceptable CI trust boundary even if arbitrary code execution is possible inside the ephemeral CI runner.

---

# 6. fetch-models.yml

This is the highest-priority workflow.

Treat it as a production deployment workflow.

Determine:

## 6.1 Trigger Security

Inspect whether it is triggered by:

* `schedule`
* `workflow_dispatch`
* `push`
* `pull_request`
* `pull_request_target`
* `workflow_call`
* other triggers

Expected preferred architecture:

```text
schedule
workflow_dispatch
    ↓
trusted branch
    ↓
production data refresh
```

Strongly flag:

```text
pull_request
+
production secrets
```

and especially:

```text
pull_request_target
+
checkout PR code
+
production secrets
```

as HIGH / CRITICAL depending on exploitability.

Do not merely search for the string `pull_request_target`. Analyze actual checkout and execution behavior.

---

# 7. Production Secret Isolation

Identify every secret referenced by workflows.

Create a table:

| Secret                     | Workflow | Job | Purpose | Required? | Risk |
| -------------------------- | -------- | --- | ------- | --------- | ---- |
| CLOUDFLARE_API_TOKEN       | ...      | ... | ...     | ...       | ...  |
| CLOUDFLARE_ACCOUNT_ID      | ...      | ... | ...     | ...       | ...  |
| CLOUDFLARE_KV_NAMESPACE_ID | ...      | ... | ...     | ...       | ...  |

Determine:

1. Which workflow can access each secret?
2. Which job can access it?
3. Is it available to PR workflows?
4. Is it available to fork PRs?
5. Is it repository-level or environment-level?
6. Is the secret scope broader than necessary?

Recommend production Environment Secrets if appropriate:

```text
production-data
    ├── CLOUDFLARE_API_TOKEN
    ├── CLOUDFLARE_ACCOUNT_ID
    └── CLOUDFLARE_KV_NAMESPACE_ID
```

Do NOT recommend unnecessary architectural changes if the existing isolation is already secure.

---

# 8. GITHUB_TOKEN Permissions

Audit every workflow for:

```yaml
permissions:
```

Determine the effective permissions.

Prefer least privilege.

For normal CI:

```yaml
permissions:
  contents: read
```

Do not allow:

```yaml
contents: write
pull-requests: write
actions: write
administration: write
```

unless explicitly required.

For every write permission, explain why it is necessary.

If no write permission is required, recommend explicitly setting:

```yaml
permissions:
  contents: read
```

rather than relying on repository defaults.

---

# 9. Third-Party GitHub Actions

Enumerate every external GitHub Action:

```yaml
uses:
  owner/action@...
```

For each action determine:

* official or third-party
* pinned by branch/tag/commit
* whether the reference is mutable
* whether the action has access to secrets
* whether the action executes arbitrary code
* whether the action is necessary

Strongly prefer immutable commit SHA pinning for security-sensitive production workflows.

Example:

```yaml
uses: actions/checkout@<commit-sha>
```

rather than:

```yaml
uses: actions/checkout@main
```

or:

```yaml
uses: some-user/action@v1
```

Do not automatically require SHA pinning for every development-only workflow. Prioritize workflows that can access production secrets.

---

# 10. Checkout Security

For each workflow inspect:

```yaml
uses: actions/checkout@...
```

Determine:

* which ref is checked out
* whether the workflow is running on the trusted branch
* whether a PR merge ref is used
* whether attacker-controlled code can be checked out
* whether that code executes before or after secrets become available

Pay particular attention to combinations such as:

```text
pull_request_target
+
checkout PR HEAD
+
run attacker-controlled code
+
secrets
```

This should be treated as a serious security boundary violation.

---

# 11. Shell Injection Audit

Search all workflows and scripts for:

```text
run:
${{ github.event.* }}
${{ github.head_ref }}
${{ github.ref }}
${{ github.event.pull_request.* }}
${{ inputs.* }}
```

Determine whether untrusted values are interpolated directly into shell commands.

Example risky pattern:

```yaml
run: |
  echo "${{ github.event.pull_request.title }}"
```

Determine whether values should instead be passed through environment variables and safely quoted.

Also inspect Python / Node subprocess usage for:

```python
subprocess.run(..., shell=True)
os.system(...)
```

and equivalent Node.js patterns.

---

# 12. Data Pipeline Supply-Chain Audit

Inspect the complete production pipeline:

```text
fetch
→ parse
→ normalize
→ identity-match
→ enrich
→ validate
→ derive
→ snapshot
→ diff
→ reconcile
→ publish
```

Determine whether any stage can execute code from external data.

External model metadata should be treated as data, never executable instructions.

Check for:

* dynamic imports
* shell execution
* URL-derived filenames
* unsafe temporary files
* unsafe archive extraction
* unsafe YAML loading
* unsafe JSON parsing assumptions
* unsafe Markdown/HTML rendering
* dynamic package installation
* remote code execution patterns

---

# 13. External HTTP Fetching

Audit all model source fetchers.

Check:

* HTTPS enforcement
* timeout
* retry limits
* response size limits
* JSON/schema validation
* malformed response handling
* decompression bombs if applicable
* redirect behavior
* SSRF risk
* user-controlled URLs

Important:

Production fetchers should use fixed, trusted source URLs.

If a URL can be supplied through:

```text
PR input
workflow input
environment variable
model metadata
repository file
```

determine whether it can be abused as SSRF.

---

# 14. Model Metadata Security

Treat all model metadata as untrusted.

Audit:

```text
model_id
name
description
provider
owned_by
capabilities
architecture
context_length
pricing
documentation URL
source URL
```

Check whether any field is:

* rendered as HTML
* interpolated into shell
* interpolated into YAML
* interpolated into JSON
* used as a filesystem path
* used as a URL
* used as a configuration key

Pay particular attention to model IDs containing:

```text
/
:
"
'
$
`
;
&
|
..
```

The existing TFI design intentionally supports model IDs containing `/`, so do NOT treat `/` itself as invalid.

The correct requirement is:

> Preserve valid model identifiers while preventing them from becoming executable syntax.

---

# 15. Cloudflare Security

Audit Cloudflare integration.

Determine exactly what the API token can do.

Preferred principle:

```text
production data workflow
    ↓
only required Cloudflare account
    ↓
only required KV operations
```

Avoid:

```text
Global API Key
```

Avoid broad account-wide permissions unless technically required.

If Pages deployment and KV publishing use the same credential, evaluate whether they should be separated.

Preferred:

```text
Pages deployment token
    ↓
Pages only

Data publish token
    ↓
KV only
```

Do not require this split if the actual Cloudflare API architecture makes it unnecessary, but explicitly document the trade-off.

---

# 16. KV Publication Integrity

Audit:

```text
snapshot
diff
reconcile
publish
```

Verify that malformed or incomplete upstream data cannot cause destructive production deletion.

Expected behavior:

```text
invalid/incomplete fetch
        ↓
DO NOT destructive reconcile
        ↓
retain previous valid state
```

Verify:

* deterministic writes
* idempotency
* stale-key d

