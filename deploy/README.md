# Deploying chapter B

The runbook for REQ-16's last criterion: a URL a stranger can open. Target and
reasoning are in adrs/ADR-0003-deploy-target.md.

Short version: set the two secrets in your shell, then run `deploy\deploy.ps1`.
It does sections 2 to 4 and finishes by running the section 4 checks for you.
The commands are written out below as well, because a script you cannot read is
not a runbook. They are PowerShell, not bash: this machine's shell is Windows
PowerShell 5.1, where the backslash continuations in Azure's own documentation
are a parse error.

Everything below is run by the operator, on the operator's accounts. Claude does
not create accounts, does not handle credentials, and does not have them. Where
a step produces a secret, it goes straight into the platform's secret store and
into nothing else -- not into this repo, not into a chat, not into CI logs.

## 0. What you need first

- The Azure CLI, which is not installed on this machine yet. Install it, then
  open a NEW shell so the PATH change takes:

      winget install -e --id Microsoft.AzureCLI

- An Azure subscription, logged in: `az login`.
- A Neon account (free tier, chosen in ADR-0003). Create the project BEFORE
  running anything here, because the app has no database fallback: the
  entrypoint runs migrations first and `store.database_url()` raises when
  `ACTION_ENGINE_DATABASE_URL` is unset, so the container exits instead of
  serving a half-configured service. Copy the pooled connection string; it
  looks like
  `postgresql://user:password@ep-xxx.region.aws.neon.tech/neondb?sslmode=require`.
  Free-tier projects suspend when idle and wake on the next connection, which
  suits a demo and is the reason the bill stays at zero.

  The app also accepts `sqlite:///...`, which would produce a working URL in
  minutes with no Neon account at all. Do not take that shortcut. Container
  Apps storage is ephemeral and this app scales to zero, so the audit rows and
  the idempotency keys would be gone between one visitor and the next. The
  profile's claim is a system that can prove what it did; a demo that forgets
  is the counter-example, not the evidence. deploy.ps1 refuses a non-Postgres
  URL for this reason.

- Nothing else to install by hand. `az containerapp` lives in an extension and
  the CLI stops to ask about it mid-command; a subscription that has never run
  Container Apps also needs `Microsoft.App` and `Microsoft.OperationalInsights`
  registered, which is a failure that does not look like it is about
  registration. deploy.ps1's preflight does all three, and checks that Container
  Apps is actually offered in the region before it creates anything.
- A signing key for tokens. Generate it locally and keep it only in the secret
  store:
  `python -c "import secrets; print(secrets.token_urlsafe(48))"`

## 1. Publish the image -- DONE 2026-09-25

The image is built and smoke-tested by CI on every push, and pushed to GHCR on
master or a tag. Chapter B merged to master on 2026-09-25, so this step is
already done; a later release is a tag:

    git tag v0.2.0 && git push origin v0.2.0

The image is at `ghcr.io/quantummonkey/action-engine:latest` and at the commit
SHA. Note the lowercase owner: a registry rejects uppercase in a repository
name, which broke the first master run (DEVIATIONS.md, 2026-09-25).

It is already public, and no click was needed -- a package published by Actions
from a public repository inherits that visibility. Verified anonymously, with
no credentials, on 2026-09-25:

    $t = (Invoke-RestMethod 'https://ghcr.io/token?scope=repository:quantummonkey/action-engine:pull&service=ghcr.io').token
    Invoke-RestMethod 'https://ghcr.io/v2/quantummonkey/action-engine/tags/list' -Headers @{ Authorization = "Bearer $t" }

That returned `latest` plus the commit tag, which is what matters twice over:
Container Apps pulls with no registry credential, and a stranger can
`docker run` the image, which is the `publish the server` half of the MCP
criterion. The image holds only fixture data and no keys, which is what makes
that safe. If the repository is ever made private, the package follows it and
step 2 then needs a registry credential.

## 2. Create the app

    az group create --name anubis-lab --location centralindia

    az containerapp up --name action-engine --resource-group anubis-lab --location centralindia --image ghcr.io/quantummonkey/action-engine:latest --target-port 8000 --ingress external

The first run also creates a Container Apps environment, so give it a few
minutes. Scale limits are deliberately NOT on this command: `az containerapp
up` does not take `--min-replicas` or `--max-replicas` -- they belong to
`create` and `update`, and an earlier draft of this file put them here, where
they would have failed on the operator's very first command. Leaving them off
costs nothing, because the default for an HTTP app is already min 0 / max 10,
and min 0 is the line that keeps the bill at zero while nobody is looking.
Section 3 sets the ceiling. Expect a cold start of a few seconds on the first
request after an idle period; that is the trade being made on purpose, and it
is safe here only because ingress is external -- an app with no ingress and no
scale rule scales to zero with no way back up.

## 3. Give it its secrets and its ceiling

    az containerapp secret set --name action-engine --resource-group anubis-lab --secrets jwt-secret="<the key from step 0>" database-url="<the Neon connection string>"

    az containerapp update --name action-engine --resource-group anubis-lab --min-replicas 0 --max-replicas 2 --set-env-vars ACTION_ENGINE_JWT_SECRET=secretref:jwt-secret ACTION_ENGINE_DATABASE_URL=secretref:database-url ACTION_ENGINE_RATE_LIMIT=60 ACTION_ENGINE_RATE_WINDOW=60

Typing a secret on a command line puts it in your shell history. deploy.ps1
reads both from environment variables instead, which is the reason it exists.

Migrations run in the container's entrypoint, so the first start after this
update creates the tables. If that fails, the container stops rather than
serving against a half-built schema; read the logs before retrying:

    az containerapp logs show --name action-engine --resource-group anubis-lab --follow

## 4. Prove it to a stranger

    $URL = az containerapp show --name action-engine --resource-group anubis-lab --query properties.configuration.ingress.fqdn --output tsv

    Invoke-RestMethod "https://$URL/healthz"                    # status = ok
    (Invoke-WebRequest "https://$URL/openapi.json" -UseBasicParsing).Content.Substring(0, 400)
    try { Invoke-WebRequest "https://$URL/v1/tables" -UseBasicParsing } catch { [int]$_.Exception.Response.StatusCode }

The third one has to be wrapped, because PowerShell raises a 401 as a
terminating error instead of returning it. `deploy.ps1 -VerifyOnly` runs all
three, prints pass/fail against the expected code, and times each one, which is
the form worth quoting.

Those three checks are acceptance criteria 10 and 11 from the chapter B spec,
and they are what goes in the README and the post: the URL, the latency you
measure, and the test count.

## 5. What the profile may claim afterwards

Only what the URL demonstrates. Cloud Computing and Azure move from a 2015
certificate to a running service; API Development, Systems Integration,
PostgreSQL and Docker move from CLAIMED to SHOWN in skills/COVERAGE.tsv. Update
that file and regenerate the proof index the same day, or the claim and the
evidence drift apart again.

## Teardown

    az group delete --name anubis-lab --yes --no-wait

Worth knowing before you start: deleting the group is the only reliable way to
stop every meter attached to it, and it takes the app, the Container Apps
environment, its Log Analytics workspace and the stored secrets with it. It
does not touch Neon, and it does not touch the image. The URL dies with it, so
do not run this while the profile is pointing at that URL -- a dead link is
worse than no link, and the skills in COVERAGE.tsv would have to move back from
SHOWN the same day.
