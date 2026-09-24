# ADR-0003: Where chapter B is deployed

- Status: accepted 2026-09-24 (operator chose Azure)
- Date: 2026-09-24
- Requirements: REQ-16
- Relates to: ADR-0002 (Postgres is on the request path for /v1/export)

## Context

Box 1 is not done until a stranger can open a URL. The deploy also has to earn
two skills the profile currently rests on an eleven-year-old certificate for:
Cloud Computing, and one of AWS or Azure.

Two constraints that are not technical. The operator has roughly three months
of runway and a floor of USD 1,000/month, so a demo that bills monthly is a
real cost, not a rounding error. And the Azure claim on the profile is
honestly described as "2022-era" -- deploying there converts the weakest anchor
on the profile into current work, which a deploy to a third cloud would not.

Verified 2026-09-24 rather than assumed:
- Azure Container Apps includes a monthly free grant of 180,000 vCPU-seconds,
  360,000 GiB-seconds and 2 million requests per subscription, and charges
  nothing while an app is scaled to zero.
- Azure Database for PostgreSQL Flexible Server has NO free tier. The cheapest
  burstable tier (B1ms) runs about USD 12-15 a month plus storage.
- AWS App Runner has no free tier either, and bills for a provisioned instance.

So the container is effectively free on Azure and the managed database is not,
which is the whole decision in one line.

## Decision (taken 2026-09-24: Azure)

**Azure Container Apps for the service, a free-tier serverless Postgres
(Neon or equivalent) for the state.**

The operator chose Azure over AWS. The consequence worth stating plainly: the
Azure line on the profile stops being 2022-era the day the URL answers, and the
AWS row keeps resting on the NIIT certificate until something is deployed there
too. In an interview the honest sentence is "the deploy is Azure; my AWS is a
certificate and course work", and that sentence is only comfortable because the
Azure half is now real.

1. The service runs on Container Apps with minimum replicas 0. Idle costs
   nothing, and the free grant covers far more traffic than a demo will see.
2. Postgres is NOT Azure's managed offering, because paying USD 150 a year to
   hold three tables of demo state fails the only test that matters here: it
   buys no proof that a free alternative does not.
3. The served SQLite database stays baked into the image as a fixture. The
   deployment demonstrates a read-only surface; it does not host anyone's data.
4. Secrets (the JWT signing key, the database URL) are set as Container Apps
   secrets by the operator. They are never committed, never printed in CI, and
   never handled by Claude.

Accepted cost of this shape: a cold start on the first request after idle, and
a managed database outside the cloud the compute runs in, which adds a network
hop and a second vendor. Both are acceptable for a demo whose purpose is to be
opened, read, and asked about in an interview.

## Alternatives

- **AWS App Runner plus RDS.** Defensible if the operator would rather prove
  AWS, where the certificate already is. Costs more per month for the same
  proof, and leaves the Azure line on the profile stale.
- **Everything on Azure, including Postgres.** Cleanest story, one vendor, one
  bill. Revisit if there is ever income to pay for it, or if free Azure credits
  from a new subscription cover the first year.
- **Fly.io or a small VPS.** Cheapest of all and proves neither cloud claim on
  the profile. Rejected for that reason alone: the deploy exists to make a
  claim true, not merely to be reachable.

## Consequences

When this is done, four CLAIMED skills (API Development, Systems Integration,
PostgreSQL, Docker) and three anchored ones (CI/CD, Cloud Computing, Azure)
have a URL behind them, and the first four sentences of PROFILE-2027Q1.md stop
being aspirational. Until then, box 1 is not closed, whatever the test suite
says.
