# Basarat Documentation Suite

Welcome to the official technical documentation for **Basarat** — an AI-powered Investment Intelligence Platform for the **Pakistan Stock Exchange (PSX)**.

---

## 1. System Architecture at a Glance

```mermaid
flowchart TD
    subgraph ClientLayer ["Client Layer"]
        ANDROID["Android Mobile App (Kotlin / Jetpack Compose)"]
    end

    subgraph IngressTier ["Edge & Ingress"]
        NGINX["Nginx Reverse Proxy (TLS Termination, Rate Limiting)"]
    end

    subgraph ServiceFleet ["Containerized Backend Services"]
        FASTAPI["FastAPI API Server (Uvicorn ASGI)<br/>• 22 Domain Routers<br/>• Correlation ID (X-Request-ID)<br/>• SlowAPI Rate Limiting<br/>• RAG AI Copilot (Groq LLM)"]
        CELERY_W["Celery Distributed Workers<br/>• Post-Close Automated Pipeline<br/>• Multi-Source News Ingestion<br/>• FinBERT Sentiment Scoring<br/>• Price & Risk Alert Monitors"]
        CELERY_B["Celery Beat Scheduler<br/>(Mon-Fri Intraday & Post-Market Crons)"]
    end

    subgraph MLSubsystem ["AI / ML Subsystems"]
        GRU_XGB["Hybrid Ensemble Predictor<br/>(Bidirectional GRU + XGBoost Classifier)"]
        FINBERT["FinBERT Financial Sentiment Engine"]
        QUANT["Quant Recommendation Engine<br/>(Technical + Fundamental + Forecast + Sentiment)"]
    end

    subgraph PersistenceTier ["Data & Cache Tier"]
        POSTGRES[("PostgreSQL 16 Database<br/>(SQLAlchemy Async ORM / asyncpg)")]
        REDIS[("Redis 7 In-Memory Cache & Broker<br/>(Pub/Sub, Locks, Caches, Celery Queues)")]
    end

    ANDROID -->|HTTPS / WSS| NGINX
    NGINX -->|Reverse Proxy (Port 8000)| FASTAPI
    FASTAPI --> MLSubsystem
    FASTAPI --> POSTGRES
    FASTAPI --> REDIS
    CELERY_B -->|Task Dispatch| REDIS
    REDIS -->|Task Consumption| CELERY_W
    CELERY_W --> MLSubsystem
    CELERY_W --> POSTGRES
    CELERY_W --> REDIS
    REDIS -->|Live Quote Pub/Sub| FASTAPI
```

---

## 2. Documentation Sitemap & Reading Paths

The documentation is organized into 9 numbered modules plus core engineering specifications:

| Section | Description | Key Documents |
|---|---|---|
| **[01-Project](file:///d:/FYP/Basarat-fyp-official/docs/01-project/)** | Product scope, SDLC methodology, functional and non-functional requirements | **[Software Development Life Cycle (SDLC)](file:///d:/FYP/Basarat-fyp-official/docs/01-project/software-development-life-cycle.md)**, [Project Overview](file:///d:/FYP/Basarat-fyp-official/docs/01-project/project-overview.md), [Functional Requirements](file:///d:/FYP/Basarat-fyp-official/docs/01-project/functional-requirements.md), [NFRs](file:///d:/FYP/Basarat-fyp-official/docs/01-project/non-functional-requirements.md) |
| **[02-Architecture](file:///d:/FYP/Basarat-fyp-official/docs/02-architecture/)** | High & low-level architecture, C4 diagrams, ER diagrams, ADRs | **[Software Design Document (SDD)](file:///d:/FYP/Basarat-fyp-official/docs/02-architecture/software-design-document.md)**, [System Architecture (HLD)](file:///d:/FYP/Basarat-fyp-official/docs/02-architecture/system-architecture.md), [API Architecture (LLD)](file:///d:/FYP/Basarat-fyp-official/docs/02-architecture/api-architecture.md), [Database Design](file:///d:/FYP/Basarat-fyp-official/docs/02-architecture/database-design.md), [ADR Decisions](file:///d:/FYP/Basarat-fyp-official/docs/02-architecture/decisions/) |
| **[03-API](file:///d:/FYP/Basarat-fyp-official/docs/03-api/)** | Complete endpoint catalog, authentication, error contracts | [API Overview](file:///d:/FYP/Basarat-fyp-official/docs/03-api/api-overview.md), [Authentication](file:///d:/FYP/Basarat-fyp-official/docs/03-api/authentication.md), [Error Handling](file:///d:/FYP/Basarat-fyp-official/docs/03-api/error-handling.md), [API Conventions](file:///d:/FYP/Basarat-fyp-official/docs/03-api/api-conventions.md) |
| **[04-Development](file:///d:/FYP/Basarat-fyp-official/docs/04-development/)** | Local environment setup, codebase layout, coding standards | [Project Structure](file:///d:/FYP/Basarat-fyp-official/docs/04-development/project-structure.md), [Dev Setup](file:///d:/FYP/Basarat-fyp-official/docs/04-development/development-setup.md), [Environment Variables](file:///d:/FYP/Basarat-fyp-official/docs/04-development/environment-variables.md), [Coding Standards](file:///d:/FYP/Basarat-fyp-official/docs/04-development/coding-standards.md) |
| **[05-Security](file:///d:/FYP/Basarat-fyp-official/docs/05-security/)** | Security architecture, RBAC authorization, PII data protection | [Security Architecture](file:///d:/FYP/Basarat-fyp-official/docs/05-security/security.md), [Authorization & RBAC](file:///d:/FYP/Basarat-fyp-official/docs/05-security/authorization.md), [Data Protection](file:///d:/FYP/Basarat-fyp-official/docs/05-security/data-protection.md) |
| **[06-Testing](file:///d:/FYP/Basarat-fyp-official/docs/06-testing/)** | Pytest suites, test plans, live endpoint audit verification | [Testing Strategy](file:///d:/FYP/Basarat-fyp-official/docs/06-testing/testing-strategy.md), [Test Plan](file:///d:/FYP/Basarat-fyp-official/docs/06-testing/test-plan.md), [Test Cases](file:///d:/FYP/Basarat-fyp-official/docs/06-testing/test-cases.md) |
| **[07-Deployment](file:///d:/FYP/Basarat-fyp-official/docs/07-deployment/)** | Docker Compose, AWS EC2, Blue-Green rollout, CI/CD pipeline | [Deployment Guide](file:///d:/FYP/Basarat-fyp-official/docs/07-deployment/deployment.md), [Infrastructure](file:///d:/FYP/Basarat-fyp-official/docs/07-deployment/infrastructure.md), [CI/CD](file:///d:/FYP/Basarat-fyp-official/docs/07-deployment/ci-cd.md), [Configuration](file:///d:/FYP/Basarat-fyp-official/docs/07-deployment/configuration.md) |
| **[08-Operations](file:///d:/FYP/Basarat-fyp-official/docs/08-operations/)** | Observability, health probes, logging, troubleshooting, runbooks | [Monitoring & Health](file:///d:/FYP/Basarat-fyp-official/docs/08-operations/monitoring.md), [Logging](file:///d:/FYP/Basarat-fyp-official/docs/08-operations/logging.md), [Troubleshooting](file:///d:/FYP/Basarat-fyp-official/docs/08-operations/troubleshooting.md), [Production Review](file:///d:/FYP/Basarat-fyp-official/docs/08-operations/production-review-2026-10-03.md) |
| **[09-AI-ML](file:///d:/FYP/Basarat-fyp-official/docs/09-ai-ml/)** | Dedicated AI/ML lifecycle, feature engineering, models, results | [AI/ML Index](file:///d:/FYP/Basarat-fyp-official/docs/09-ai-ml/README.md), [Dataset](file:///d:/FYP/Basarat-fyp-official/docs/09-ai-ml/01-dataset.md), [Preprocessing](file:///d:/FYP/Basarat-fyp-official/docs/09-ai-ml/02-data-preprocessing.md), [Feature Engineering](file:///d:/FYP/Basarat-fyp-official/docs/09-ai-ml/03-feature-engineering.md), [ML Models](file:///d:/FYP/Basarat-fyp-official/docs/09-ai-ml/04-ml-models.md), [Training](file:///d:/FYP/Basarat-fyp-official/docs/09-ai-ml/05-model-training.md), [Evaluation & Results](file:///d:/FYP/Basarat-fyp-official/docs/09-ai-ml/06-model-evaluation-results.md), [Serving & Deployment](file:///d:/FYP/Basarat-fyp-official/docs/09-ai-ml/07-ml-deployment-inference.md) |

---

### Recommended Reading Paths

- **FYP Panel & Evaluators**: Start with **[SDLC Methodology](file:///d:/FYP/Basarat-fyp-official/docs/01-project/software-development-life-cycle.md)** -> **[Software Design Document (SDD)](file:///d:/FYP/Basarat-fyp-official/docs/02-architecture/software-design-document.md)** -> **[AI/ML Evaluation & Results](file:///d:/FYP/Basarat-fyp-official/docs/09-ai-ml/06-model-evaluation-results.md)** -> **[Viva Preparation Guide](file:///d:/FYP/Basarat-fyp-official/docs/09-ai-ml/viva-preparation-guide.md)**.
- **Backend Developers**: Start with [Project Structure](file:///d:/FYP/Basarat-fyp-official/docs/04-development/project-structure.md) -> [Development Setup](file:///d:/FYP/Basarat-fyp-official/docs/04-development/development-setup.md) -> [Software Design Document (SDD)](file:///d:/FYP/Basarat-fyp-official/docs/02-architecture/software-design-document.md) -> [Database Design](file:///d:/FYP/Basarat-fyp-official/docs/02-architecture/database-design.md).
- **Mobile Engineers (Android)**: Review [API Overview](file:///d:/FYP/Basarat-fyp-official/docs/03-api/api-overview.md) -> [Authentication](file:///d:/FYP/Basarat-fyp-official/docs/03-api/authentication.md) -> [API Conventions](file:///d:/FYP/Basarat-fyp-official/docs/03-api/api-conventions.md) -> [Error Handling](file:///d:/FYP/Basarat-fyp-official/docs/03-api/error-handling.md).
- **ML / AI Engineers**: Read [AI/ML Index](file:///d:/FYP/Basarat-fyp-official/docs/09-ai-ml/README.md) -> [Feature Engineering](file:///d:/FYP/Basarat-fyp-official/docs/09-ai-ml/03-feature-engineering.md) -> [ML Models](file:///d:/FYP/Basarat-fyp-official/docs/09-ai-ml/04-ml-models.md) -> [Model Evaluation / Results](file:///d:/FYP/Basarat-fyp-official/docs/09-ai-ml/06-model-evaluation-results.md) -> [Serving](file:///d:/FYP/Basarat-fyp-official/docs/09-ai-ml/07-ml-deployment-inference.md).
- **DevOps / SRE**: Read [Deployment Guide](file:///d:/FYP/Basarat-fyp-official/docs/07-deployment/deployment.md) -> [CI/CD](file:///d:/FYP/Basarat-fyp-official/docs/07-deployment/ci-cd.md) -> [Monitoring](file:///d:/FYP/Basarat-fyp-official/docs/08-operations/monitoring.md) -> [Troubleshooting](file:///d:/FYP/Basarat-fyp-official/docs/08-operations/troubleshooting.md).
