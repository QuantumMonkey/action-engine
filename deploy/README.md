# Deploying chapter B

The runbook for REQ-16's last criterion: a URL a stranger can open. Target and
reasoning are in adrs/ADR-0003-deploy-target.md.

Everything below is run by the operator, on the operator's accounts. Claude does
not create accounts, does not handle credentials, and does not have them. Where
a step produces a secret, it goes straight into the platform's secret store and
into nothing else -- not into this repo, not into a chat, not into CI logs.

## 0. What you need first

- An Azure subscription and `az` CLI logged in (`az login`).
- A Neon account (free tier, chosen in ADR-0003). Create a project and copy the
  pooled connection string; it looks like
  `postgresql://user:password@ep-xxx.region.aws.neon.tech/neondb?sslmode=require`.
  Free-tier projects suspend when idle and wake on the next connection, which
  suits a demo and is the reason the bill stays at zero.
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

    T=$(curl -s 'https://ghcr.io/token?scope=repository:quantummonkey/action-engine:pull&service=ghcr.io' | jq -r .token)
    curl -s -H "Authorization: Bearer $T" https://ghcr.io/v2/quantummonkey/action-engine/tags/list

That returned `latest` plus the commit tag, which is what matters twice over:
Container Apps pulls with no registry credential, and a stranger can
`docker run` the image, which is the `publish the server` half of the MCP
criterion. The image holds only fixture data and no keys, which is what makes
that safe. If the repository is ever made private, the package follows it and
step 2 then needs a registry credential.

## 2. Create the app

    az group create --name anubis-lab --location centralindia

    az containerapp up \
      --name action-engine \
      --resource-group anubis-lab \
      --image ghcr.io/quantummonkey/action-engine:latest \
      --target-port 8000 \
      --ingress external \
      --min-replicas 0 \
      --max-replicas 2

`--min-replicas 0` is the line that keeps the bill at zero while nobody is
looking at it. Expect a cold start of a few seconds on the first request after
an idle period; that is the trade being made on purpose.

## 3. Give it its secrets

    az containerapp secret set \
      --name action-engine --resource-group anubis-lab \
      --secrets jwt-secret="<the key from step 0>" \
                database-url="<the Postgres connection string>"

    az containerapp update \
      --name action-engine --resource-group anubis-lab \
      --set-env-vars \
        ACTION_ENGINE_JWT_SECRET=secretref:jwt-secret \
        ACTION_ENGINE_DATABASE_URL=secretref:database-url \
        ACTION_ENGINE_RATE_LIMIT=60 \
        ACTION_ENGINE_RATE_WINDOW=60

Migrations run in the container's entrypoint, so the first start after this
update creates the tables. If that fails, the container stops rather than
serving against a half-built schema; read the logs before retrying:

    az containerapp logs show --name action-engine --resource-group anubis-lab --follow

## 4. Prove it to a stranger

    URL=$(az containerapp show --name action-engine --resource-group anubis-lab \
          --query properties.configuration.ingress.fqdn -o tsv)

    curl -fsS https://$URL/healthz                      # {"status":"ok",...}
    curl -fsS https://$URL/openapi.json | head -c 400   # the generated contract
    curl -s -o /dev/null -w '%{http_code}\n' https://$URL/v1/tables   # 401, not 200

Those three commands are the acceptance criteria 10 and 11 from the chapter B
spec, and they are what goes in the README and the post: the URL, the median
latency you measure, and the test count.

## 5. What the profile may claim afterwards

Only what the URL demonstrates. Cloud Computing and Azure move from a 2015
certificate to a running service; API Development, Systems Integration,
PostgreSQL and Docker move from CLAIMED to SHOWN in skills/COVERAGE.tsv. Update
that file and regenerate the proof index the same day, or the claim and the
evidence drift apart again.

## Teardown

    az group delete --name anubis-lab --yes --no-wait

Worth knowing before you start: deleting the group is the only reliable way to
stop every meter attached to it.
