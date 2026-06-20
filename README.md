# AeroInbox: AI-Powered Executive Email Assistant (Microservices)

AeroInbox is a real-world, production-ready email intelligence assistant built for managers, founders, and CEOs to minimize time spent reading and replying to emails. It connects securely to Gmail, fetches unread mail, uses state-of-the-art LLMs (Google Gemini, Azure AI Foundry, Azure OpenAI, or OpenAI) to extract structured executive summaries, classifies priorities in bulk on sync, and drafts response options.

Decomposed into a **6-tier microservices architecture** configured to deploy on a single machine or Azure Virtual Machine via Docker Compose.

---

## Architecture Diagram

```
                 Internet
                    │
                    ▼ (Port 80)
        +-----------------------+
        |  Nginx Reverse Proxy  |
        |  (Frontend Container) |
        +-----------------------+
                    │
                    ▼ (Proxy Pass /auth, /emails, /rules, or /meetings)
        +-----------------------+
        |      API Service      | (Orchestrator Gateway :8000)
        +-----------------------+
          /       /    \       \
         /       /      \       \  (Internal HTTP)
        ▼       ▼        ▼       ▼
+-----------+ +-----------+ +-----------+ +-----------+
|   Gmail   | |    AI     | |   Rule    | |  Meeting  |
|  Service  | |  Service  | |  Engine   | |  Service  |
|   :8000   | |   :8000   | |   :8000   | |   :8000   |
+-----------+ +-----------+ +-----------+ +-----------+
      │             │             │             │
      ▼             ▼             ▼             ▼
  Gmail API   LLM Providers   rules.json    meetings.db
```

---

## Folder Structure

```
aeroinbox/
├── frontend/              # React SPA (deployed to Static Web Apps)
├── services/              # Backend microservices
│   ├── api-service/       # Gateway, OAuth handling, and route orchestrator (Internal Port 8000)
│   ├── gmail-service/     # Gmail API reading, body decoding, and extraction (Internal Port 8000)
│   ├── ai-service/        # Structured email analysis using Gemini/Azure AI Foundry (Internal Port 8000)
│   ├── rule-engine/       # Configurable rules engine evaluating VIP titles, domains, keywords (Internal Port 8000)
│   └── meeting-service/   # Meeting extraction parser (ICS, URLs), calendar API, and dashboard SQLite store (Internal Port 8000)
├── infrastructure/        # Terraform IaC (if configured)
├── .github/               # CI/CD workflows (if configured)
├── docker-compose.yml     # Central container orchestration config
└── .env.example           # Environment template
```

---

## Key Features
- **Unread Email Prioritization**: Performs scoring calculations and runs AI analysis exclusively on unread emails. Read emails are automatically excluded and omitted from active prioritized queues.
- **Hybrid AI + Rule-Based Engine**: Computes a final priority score (`Final = AI Score + Rule Score + Preference Boost`) and groups emails into *Critical, High, Medium, or Low* priorities.
- **Meeting Intelligence & Calendar Dashboard**: Automatically parses emails for calendar invitations (ICS files) or natural language meeting requests (using Gemini) to extract meeting URLs, platforms (Google Meet, Zoom, Teams), times, and participants. Adds meeting cards directly to email details and populates a dedicated **Meetings Calendar Dashboard** (grouped into *Today, Tomorrow, Upcoming, and Missed*).
- **Spam Folder Intelligence**: Scans the spam folder for false positives. Employs quick actions: *Move to Inbox*, *Mark Safe Sender*, *Ignore*.
- **Multi-Account Support**: Connects and processes synchronization for multiple Gmail accounts in parallel. Includes a Unified Inbox view, individual accounts badges, and a switcher.
- **Light & Dark Themes**: Provides responsive dark and light modes with automatic system preference detection and persistence.
- **In-App Notifications**: Real-time notification center (toast alerts) for critical unread emails, spam false positives, and deadline warnings.
- **Stateless OAuth 2.0 Auth**: Fully secure, token-refresh supported auth loop.
- **Multi-Provider LLM Integration**: Supports **Google Gemini**, **Azure OpenAI**, **Azure AI Foundry (Serverless APIs)**, and standard **OpenAI** (such as `gpt-4o-mini` or `gpt-4.1-mini`). Auto-detects configuration or routes using the `AI_PROVIDER` setting.
- **Single Public Port (Port 80)**: Only Nginx is exposed. All service-to-service routing happens inside a private Docker bridge network (`aero-net`).

---

## Prerequisites
- **Docker** and **Docker Compose (v2+)** (Do not use legacy `docker-compose` v1)
- **Google Cloud Platform Project** with Gmail API enabled and OAuth Web Application credentials set up.
- **AI Credentials**: An API key or endpoint from **Google Gemini**, **Azure AI Foundry**, **Azure OpenAI**, or **OpenAI**.

---

## Local Setup & Run

1. Clone the repository:
   ```bash
   git clone <repository_url> aeroinbox
   cd aeroinbox
   ```

2. Configure your environment variables. Copy `.env.example` to `.env` and fill in the values:
   ```bash
   cp .env.example .env
   ```
   *For local development, keep `GOOGLE_REDIRECT_URI=http://localhost:3000/auth/callback` and `FRONTEND_URL=http://localhost:3000`.*

3. Spin up the backend containers using **Compose v2**:
   ```bash
   docker compose up -d
   ```

4. Start the frontend locally:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

5. Open `http://localhost:3000` in your browser.

---

## AI Provider Setup

AeroInbox supports multiple LLM providers. In your `.env` file, set `AI_PROVIDER` and the relevant keys.

### 1. Google Gemini (Default)
```env
AI_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key_from_ai_studio
```

### 2. Azure AI Foundry (Serverless APIs / Model Catalog)
Copy the **Project endpoint** and **API Key** from your Azure AI Foundry model deployment tab:
```env
AI_PROVIDER=azure_ai_foundry
AZURE_AI_FOUNDRY_API_KEY=your_azure_ai_foundry_api_key
AZURE_AI_FOUNDRY_ENDPOINT=https://your-endpoint.services.ai.azure.com/
AZURE_AI_FOUNDRY_MODEL=gpt-4.1-mini # (or your model name)
```

### 3. Azure OpenAI Service
Configure using your Azure OpenAI resource endpoint, deployment name, and API key:
```env
AI_PROVIDER=azure_openai
AZURE_OPENAI_API_KEY=your_azure_openai_key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o-mini
AZURE_OPENAI_API_VERSION=2024-02-15-preview
```

### 4. OpenAI / Custom OpenAI-compatible APIs
```env
AI_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
```

---

## Azure VM Deployment

### 1. VM Sizing & Firewalls
- **Instance**: `Standard_B2s` (2 vCPUs, 4GB RAM) or `Standard_B1ms` (1 vCPU, 2GB RAM) running Ubuntu 24.04 LTS.
- **Open Ports**: Open port **80** (HTTP) and port **22** (SSH) in the Azure Network Security Group (NSG) configurations.

### 2. Install Docker & Compose on Ubuntu VM
Connect to your VM via SSH and run:
```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER
```
*(Log out of the SSH session and log back in for permissions to take effect)*.

### 3. Clone and Start Services
```bash
# Clone the repository
git clone <repository_url> aeroinbox
cd aeroinbox

# Configure environment
cp .env.example .env
nano .env
```
> [!IMPORTANT]
> Change the variables in `.env` to match your VM's public IP:
> - `GOOGLE_REDIRECT_URI=http://<YOUR_VM_PUBLIC_IP>/auth/callback`
> - `FRONTEND_URL=http://<YOUR_VM_PUBLIC_IP>`

Build and run using **Compose v2**:
```bash
docker compose build --build-arg VITE_API_URL=""
docker compose up -d
```
Inspect health checks using `docker compose ps`. Access the app at `http://<YOUR_VM_PUBLIC_IP>`.

---

## Azure Enterprise Cloud Deployment (Terraform + Container Apps + SWA)

AeroInbox can be deployed to a secure, production-grade Azure Hybrid Enterprise architecture using Terraform Infrastructure as Code (IaC).

### Architecture Components
* **Azure Static Web Apps (SWA)**: Serves the compiled React frontend client with optimized caching and CSP security.
* **Azure Container Apps**: Runs the 5 python microservice containers in a managed environment with service-to-service VNet communication.
* **Azure Key Vault**: Stores credentials safely using Managed Identity RBAC access (avoiding hardcoded secrets).
* **Azure Database for PostgreSQL**: VNet-delegated flexible server storing Rule Engine configurations and calendars.
* **Redis Sidecar**: Run alongside the `api-service` container as a local, secure cache layer for sessions.

### Deployment Instructions

#### 1. Prerequisites
* [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) (logged in using `az login`)
* [Terraform CLI](https://developer.hashicorp.com/terraform/downloads) (v1.5.0+)
* Azure Subscription permissions (Contributor/User Access Administrator roles)

#### 2. Infrastructure Provisioning
1. Navigate to the `infrastructure/` directory:
   ```bash
   cd infrastructure
   ```
2. Copy the variable environment template and modify it for your deployment (e.g. settings in `environments/dev/terraform.tfvars`):
   ```bash
   cp environments/dev/terraform.tfvars environments/dev/terraform.tfvars.local
   ```
3. Initialize the Terraform state backend:
   ```bash
   terraform chdir=infrastructure init -var-file="environments/dev/terraform.tfvars"
   ```
4. Run the plan command to review pending resources:
   ```bash
   terraform plan -var-file="environments/dev/terraform.tfvars"
   ```
5. Apply changes to deploy active cloud resources:
   ```bash
   terraform apply -var-file="environments/dev/terraform.tfvars" -auto-approve
   ```

#### 3. Update Key Vault Secrets
After deployment completes, fetch your key vault name from the terraform output and set your production secrets via Azure CLI or portal:
```bash
az keyvault secret set --vault-name <KEY_VAULT_NAME> --name google-client-id --value "<YOUR_CLIENT_ID>"
az keyvault secret set --vault-name <KEY_VAULT_NAME> --name google-client-secret --value "<YOUR_CLIENT_SECRET>"
az keyvault secret set --vault-name <KEY_VAULT_NAME> --name gemini-api-key --value "<YOUR_GEMINI_KEY>"
```

#### 4. Build & Deploy Frontend
1. Navigate to the `frontend/` directory:
   ```bash
   cd ../frontend
   ```
2. Create or verify `frontend/.env.production` containing your container app endpoint:
   ```env
   VITE_API_URL=https://api-service.<CONTAINER_APP_ENV_DOMAIN>
   ```
3. Build the static assets:
   ```bash
   npm run build
   ```
4. Deploy the build outputs to SWA using the static web apps CLI:
   ```bash
   npx @azure/static-web-apps-cli deploy ./dist --deployment-token <SWA_DEPLOYMENT_TOKEN> --env production
   ```

*(See [architecture_overview.md](file:///c:/Users/ASUS/OneDrive/Desktop/Ai_Assistan_Email/architecture_overview.md) for more details).*


