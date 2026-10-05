# Repository & Project Structure

The Basarat repository is organized into distinct functional layers separating API presentation, domain services, database models, ML training & serving pipelines, asynchronous background tasks, testing suites, and deployment assets.

```
Basarat-fyp-official/
│
├── .github/
│   └── workflows/
│       └── deploy-ec2.yml          # GitHub Actions CI/CD automated pipeline
│
├── docs/                           # Master Documentation Directory
│   ├── README.md                   # Documentation Index & Sitemap
│   ├── 01-project/                 # Project Requirements & Scope
│   ├── 02-architecture/            # SDD, HLD, LLD, Database Design & ADRs
│   ├── 03-api/                     # API Reference, Authentication & Contracts
│   ├── 04-development/             # Setup Guides, Environment & Standards
│   ├── 05-security/                # Security, RBAC & Data Protection
│   ├── 06-testing/                 # Test Plans, Pytest Suite & Coverage
│   ├── 07-deployment/              # Docker, Infrastructure & Blue-Green Rollout
│   ├── 08-operations/              # Monitoring, Logging, Troubleshooting & Runbooks
│   └── 09-ai-ml/                   # Complete AI/ML Lifecycle Documentation
│
├── data/                           # Global Data Assets & Training Corpus
│   ├── raw/                        # Historical raw PSX equity OHLCVs
│   └── features/                   # Normalized parquet feature datasets (2020-2026)
│
└── backend/                        # Backend Application Root
    │
    ├── app/                        # FastAPI Application Package
    │   ├── api/                    # API Presentation & Route Handlers
    │   │   └── v1/                 # 22 Domain Routers (Auth, Stocks, Forecast, etc.)
    │   │
    │   ├── core/                   # Infrastructure, Security, Rate Limiter & Exceptions
    │   ├── db/                     # SQLAlchemy Async Session & Declarative Base
    │   ├── models/                 # SQLAlchemy 2.0 ORM Entity Models
    │   ├── schemas/                # Pydantic v2 Request / Response Schemas
    │   ├── services/               # 32 Domain Business Services & News Pipeline
    │   ├── tasks/                  # Celery Background Workers & Schedulers
    │   │
    │   ├── ml/                     # Machine Learning Package
    │   │   ├── README.md           # Package overview & navigation guide
    │   │   ├── serving/            # [ACTIVE] Dual-model loader & real-time inference
    │   │   ├── v3/                 # [ACTIVE] Feature engineering v3 & multi-horizon trainer
    │   │   ├── v2/                 # [ARCHIVE] Previous v2 pipeline
    │   │   ├── training/           # [ARCHIVE] Initial v1 GRU experiments
    │   │   └── training_xgb/       # [ARCHIVE] Initial v1 XGBoost experiments
    │   │
    │   ├── main.py                 # FastAPI Application Initialization & Lifespan
    │   └── celery_app.py           # Celery Worker Configuration & Beat Schedules
    │
    ├── models/                     # Packaged ML Model Weights & Manifests
    │   ├── README.md               # Model catalog & artifact reference
    │   ├── production/
    │   │   └── v3/                 # [ACTIVE PRODUCTION] Attention-BiGRU & XGBoost (5D, 10D, 20D)
    │   └── archive/                # Legacy models & experimental archives
    │
    ├── scripts/                    # Operational & Diagnostic Utilities
    │   ├── README.md               # Index of all operational, seeding, sync, and testing scripts
    │   ├── init_db_tables.py       # Database schema initialization
    │   ├── seed_admin.py           # Admin account seeding
    │   ├── seed_all_fundamentals.py# Fundamentals seeder
    │   ├── sync_friday_prices.py   # Friday market session synchronization
    │   ├── sync_kse100_database.py # KSE-100 constituents sync
    │   ├── test_live_ai_ml_endpoints.py # AI/ML live endpoint test
    │   ├── test_live_chatbot_streaming.py # Chatbot SSE streaming test
    │   ├── run_live_oracle_comprehensive_audit.py # Comprehensive live audit
    │   ├── validate_recommendation_engine.py # Recommendation engine validator
    │   ├── run_ml_pipeline.py      # ML pipeline orchestration
    │   └── archive/                # Archived one-off / scratch / inspection scripts
    │
    ├── tests/                      # Automated Pytest Suite (unit, api, e2e)
    ├── deploy/                     # Deployment Scripts & Nginx Configurations
    ├── Dockerfile                  # Multi-stage production container definition
    ├── docker-compose.yml          # Local development compose
    ├── docker-compose.production.yml # Production compose stack
    ├── requirements.txt            # Direct dependencies
    └── requirements.lock           # Locked dependencies with SHA-256 hashes
```
