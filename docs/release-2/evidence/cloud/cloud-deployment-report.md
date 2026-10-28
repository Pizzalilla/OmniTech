# Cloud deployment report (Azure Container Apps)

- Deployed: 2026-10-28T02:17:54Z (commit c4f96ec, image tag c4f96eca1f5dbe612f23891d33961e7ab2873751)
- Region / resource group: australiaeast / omnitech-rg
- Home page: https://omnitech-home.happypebble-4f98f20b.australiaeast.azurecontainerapps.io
- Smoke test: **15/15 checks passed**

AI-Mode, MCP, RAG and the Multi-Agent Server are **disabled by default** in this deployment (Ollama is not deployed and every AI address points to a non-resolving `.invalid` host).
Every app is behind the security gateway; these checks log in. See `cloud-security-report.md` for the security validation.

| Service | Check | Request | Expected | Got | Result | Time |
|---|---|---|---|---|---|---|
| home | Home page lists every feature | `GET https://omnitech-home.happypebble-4f98f20b.australiaeast.azurecontainerapps.io/` | 200 | 200 | PASS | 605 ms |
| student-1 | Catalog page | `GET https://omnitech-student-1.happypebble-4f98f20b.australiaeast.azurecontainerapps.io/` | 200 | 200 | PASS | 812 ms |
| student-1 | Read products | `GET https://omnitech-student-1.happypebble-4f98f20b.australiaeast.azurecontainerapps.io/api/products` | 200 | 200 | PASS | 600 ms |
| student-1 | AI summary disabled by default | `POST https://omnitech-student-1.happypebble-4f98f20b.australiaeast.azurecontainerapps.io/api/products/1/ai-summary` | 503 | 503 | PASS | 610 ms |
| student-1 | Multi-Agent disabled by default | `GET https://omnitech-student-1.happypebble-4f98f20b.australiaeast.azurecontainerapps.io/api/multi-agent/history` | 503 | 503 | PASS | 602 ms |
| student-2 | Customers page | `GET https://omnitech-student-2.happypebble-4f98f20b.australiaeast.azurecontainerapps.io/` | 200 | 200 | PASS | 604 ms |
| student-2 | Read customers | `GET https://omnitech-student-2.happypebble-4f98f20b.australiaeast.azurecontainerapps.io/api/customers` | 200 | 200 | PASS | 602 ms |
| student-3 | Consultant page | `GET https://omnitech-student-3.happypebble-4f98f20b.australiaeast.azurecontainerapps.io/` | 200 | 200 | PASS | 839 ms |
| student-3 | Create session | `POST https://omnitech-student-3.happypebble-4f98f20b.australiaeast.azurecontainerapps.io/api/sessions` | 201 | 201 | PASS | 644 ms |
| student-3 | Read sessions | `GET https://omnitech-student-3.happypebble-4f98f20b.australiaeast.azurecontainerapps.io/api/sessions` | 200 | 200 | PASS | 617 ms |
| student-3 | AI services disabled by default | `POST https://omnitech-student-3.happypebble-4f98f20b.australiaeast.azurecontainerapps.io/api/rag/query` | 200 | 200 | PASS | 596 ms |
| student-3 | Multi-Agent disabled by default | `GET https://omnitech-student-3.happypebble-4f98f20b.australiaeast.azurecontainerapps.io/api/multi-agent/history` | 503 | 503 | PASS | 609 ms |
| student-4 | Cart page | `GET https://omnitech-student-4.happypebble-4f98f20b.australiaeast.azurecontainerapps.io/` | 200 | 200 | PASS | 623 ms |
| student-5 | Warranty page | `GET https://omnitech-student-5.happypebble-4f98f20b.australiaeast.azurecontainerapps.io/` | 200 | 200 | PASS | 618 ms |
| student-5 | Read tickets | `GET https://omnitech-student-5.happypebble-4f98f20b.australiaeast.azurecontainerapps.io/tickets` | 200 | 200 | PASS | 1001 ms |

## Final human release decision

Filled in after the agentic-loop Cloud Deployment Review:

- Decision (approve / approve with conditions / reject): **Approve.** Recorded in the Multi-Agent workflow as "correct" (agent summary corrected, release approved)
- Decided by: Kartikay Singh
- Date: 28 October 2026
- Agentic-loop Cloud Deployment Review: workflow `wf-efa27b7b`, Reviewer verdict "needs changes"
  (`../agentic-loop/cloud-deployment-review.json`, full record and audit trail in
  `../agentic-loop/cloud-deployment-review-decision.txt`)
- Reason: The Worker misreported the smoke-test figure (it is 15/15, and the security validation is 93/93)
  and said CRUD could not be verified. CRUD is evidenced by the smoke test's create (POST session 201) and
  read checks, with update and delete covered by each student's CI endpoint tests. The AI-off settings are
  confirmed by the deployment configuration (`*_ENABLED=false`, AI hosts pointing to `.invalid`). All smoke
  and security checks pass on commit c4f96ec, so the release is approved.
