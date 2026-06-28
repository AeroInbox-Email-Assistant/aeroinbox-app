# AeroInbox Project Rules

## Project Architecture Overview
AeroInbox is a multi-microservice AI email assistant deployed on Azure AKS using a GitOps workflow.

### Repositories
- **App Code**: `AeroInbox-Email-Assistant/aeroinbox-app` (Python FastAPI services + React frontend)
- **Helm Config**: `AeroInbox-Email-Assistant/aeroinbox-helm` (Kubernetes manifests via Helm charts)
- **Infrastructure**: Local at `aeroinbox-terraform/` (12 custom Terraform modules)

### Services
| Service | Port | Role |
|---|---|---|
| `api-service` | 8000 | Public-facing gateway, routes all frontend requests |
| `gmail-service` | 8000 | OAuth token refresh, Gmail sync via Azure Service Bus |
| `ai-service` | 8000 | LLM email prioritization using Gemini |
| `rule-engine` | 8000 | User-defined email filtering rules |
| `meeting-service` | 8000 | Email meeting detection, calendar, reminders |
| `frontend` | 80 | React SPA served via nginx |

---

## Deployment Flow (GitOps via ArgoCD)
1. Code is pushed to `aeroinbox-app` -> GitHub Actions builds Docker image
2. Image is pushed to ACR (`acraeroinboxprod.azurecr.io`) tagged with Git Commit SHA
3. CI/CD pipeline updates `environments/production/values.yaml` in `aeroinbox-helm` with the new image tag
4. ArgoCD (running in AKS, namespace: `argocd`) polls `aeroinbox-helm` every 3 minutes
5. ArgoCD detects the tag change and applies a rolling update to the AKS cluster

### Key Files for Deployments
- `aeroinbox-helm/values.yaml` - Global defaults for all services
- `aeroinbox-helm/environments/production/values.yaml` - Production image tags and replica overrides
- `aeroinbox-helm/argocd/applications/aeroinbox.yaml` - ArgoCD Application definition

---

## Known Patterns & Decisions

### KEDA Autoscaling (meeting-service)
- The `meeting-service` uses KEDA to autoscale based on Azure Service Bus queue depth (`meeting-reminders` queue)
- **maxReplicas is configured in `values.yaml`** under `meeting-service.autoscaling.maxReplicas` (currently set to 2)
- **Do not hardcode** values in `keda-scaler.yaml`. Always use `{{ .Values.autoscaling.maxReplicas | default 2 }}`
- If meeting-service has too many pods (e.g. 10), KEDA scaled it up because Service Bus auth failed or queue was backlogged
- Check: `kubectl describe scaledobject aeroinbox-meeting-service-scaler -n production`

### Frontend Meeting Banner (Bug Fix - June 2026)
- The purple "Add to Calendar" banner is triggered by matching `selectedEmail.id` with `meeting.source_email_id` in the database
- **Root cause of banner not showing**: `_handle_existing_meeting()` previously returned early without updating `source_email_id` to the new email ID
- **Fix location**: `services/meeting-service/main.py` - `_handle_existing_meeting()` now always updates `source_email_id` and `description` from the latest parsed email

### Kubernetes Access
- The AKS cluster API is **private** - kubectl commands must be run from the **Bastion VM Jumpbox**
- SSH access: via Azure Bastion in the Azure Portal -> VM: `vm-jumpbox` in `rg-aeroinbox-prod`
- Local `kubectl` commands from the developer's Windows machine will fail with DNS resolution errors (expected by design)

### Key Vault + Workload Identity Flow
- Pods authenticate to Azure Key Vault using **Azure Workload Identity** (no stored passwords)
- Each service has a dedicated User-Assigned Managed Identity (created in `modules/identity`)
- Secrets are mounted via **SecretProviderClass** (CSI driver) in `aeroinbox-helm/charts/shared/templates/secretproviderclass.yaml`
- Pod annotations must include `azure.workload.identity/use: "true"` for identity binding to work

### Monitoring & Observability
- **Application Insights**: `appi-aeroinbox-production` in `rg-aeroinbox-prod` - HTTP traces, exceptions, LLM call latency
- **Log Analytics**: `log-aeroinbox-production` - Container stdout, KQL queryable
- **Prometheus**: Each pod exposes `/metrics` at port 8000 with annotations `prometheus.io/scrape: "true"`

---

## Important Constraints
- Never run `terraform destroy` without explicit user confirmation - this will delete all production Azure resources
- All kubectl operations on production must be done through the Bastion Jumpbox VM, not local terminals
- Service Bus connection strings are stored in Key Vault - never hardcode them in Helm values or Kubernetes secrets manifests
- The `aeroinbox-terraform/` folder is NOT yet on GitHub - remind the user to push it if switching machines
