# Cloud deployment report (Azure Container Apps)

- Deployed: 2026-10-19T12:27:57Z (commit ffa47c9, image tag ffa47c9-dirty-20261019232548)
- Region / resource group: australiaeast / omnitech-rg
- Home page: https://omnitech-home.happypebble-4f98f20b.australiaeast.azurecontainerapps.io
- Smoke test: **12/12 checks passed**

AI-Mode, MCP, RAG and the Multi-Agent Server are **disabled by default** in this deployment (Ollama is not deployed and every AI address points to a non-resolving `.invalid` host).

| Service | Check | Request | Expected | Got | Result | Time |
|---|---|---|---|---|---|---|
| home | Home page lists every feature | `GET https://omnitech-home.happypebble-4f98f20b.australiaeast.azurecontainerapps.io/` | 200 | 200 | PASS | 45 ms |
| student-1 | Catalog page | `GET https://omnitech-student-1.happypebble-4f98f20b.australiaeast.azurecontainerapps.io/` | 200 | 200 | PASS | 58 ms |
| student-1 | Read products | `GET https://omnitech-student-1.happypebble-4f98f20b.australiaeast.azurecontainerapps.io/api/products` | 200 | 200 | PASS | 36 ms |
| student-2 | Customers page | `GET https://omnitech-student-2.happypebble-4f98f20b.australiaeast.azurecontainerapps.io/` | 200 | 200 | PASS | 121 ms |
| student-2 | Read customers | `GET https://omnitech-student-2.happypebble-4f98f20b.australiaeast.azurecontainerapps.io/api/customers` | 200 | 200 | PASS | 43 ms |
| student-3 | Consultant page | `GET https://omnitech-student-3.happypebble-4f98f20b.australiaeast.azurecontainerapps.io/` | 200 | 200 | PASS | 40 ms |
| student-3 | Create session | `POST https://omnitech-student-3.happypebble-4f98f20b.australiaeast.azurecontainerapps.io/api/sessions` | 201 | 201 | PASS | 59 ms |
| student-3 | Read sessions | `GET https://omnitech-student-3.happypebble-4f98f20b.australiaeast.azurecontainerapps.io/api/sessions` | 200 | 200 | PASS | 36 ms |
| student-3 | AI services disabled by default | `POST https://omnitech-student-3.happypebble-4f98f20b.australiaeast.azurecontainerapps.io/api/rag/query` | 200 | 200 | PASS | 37 ms |
| student-4 | Cart page | `GET https://omnitech-student-4.happypebble-4f98f20b.australiaeast.azurecontainerapps.io/` | 200 | 200 | PASS | 177 ms |
| student-5 | Warranty page | `GET https://omnitech-student-5.happypebble-4f98f20b.australiaeast.azurecontainerapps.io/` | 200 | 200 | PASS | 36 ms |
| student-5 | Read tickets | `GET https://omnitech-student-5.happypebble-4f98f20b.australiaeast.azurecontainerapps.io/tickets` | 200 | 200 | PASS | 49 ms |

## Final human release decision

Filled in after the agentic-loop Cloud Deployment Review:

- Decision (approve / approve with conditions / reject):
- Decided by:
- Date:
- Reason:
