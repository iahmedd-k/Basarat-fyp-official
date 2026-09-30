# Infrastructure Architecture & Topologies — Basarat

## 1. Overview & Infrastructure Topologies

Basarat is designed with an infrastructure topology that transitions smoothly from a local containerized developer environment to a cost-effective single-host cloud deployment, and scales out to an enterprise multi-tier cloud infrastructure.

---

## 2. Infrastructure Comparison Matrix

| Component | Local Development Topology | Current Production Topology (Self-Hosted EC2) | Recommended Enterprise Production Topology |
|---|---|---|---|
| **Host Compute** | Local Workstation (Docker Desktop) | AWS EC2 `t3.large` (Ubuntu 22.04 LTS) | AWS ECS / EKS Multi-Node Cluster (Auto-Scaling) |
| **Ingress / Load Balancer**| Direct Host Port Binding (`:8000`, `:5173`) | Nginx / Caddy Reverse Proxy + Let's Encrypt TLS | AWS Application Load Balancer (ALB) + AWS ACM TLS |
| **Application Server** | Uvicorn (`--reload`, 1 worker) | Uvicorn (1 worker inside Docker) | Gunicorn / Uvicorn Cluster (4+ workers per node) |
| **Async Task Workers** | Celery Worker (Concurrency 2) | Celery Worker (Concurrency 1, max-tasks 1) | Dedicated Celery Worker Auto-Scaling Group |
| **Cron Scheduler** | Celery Beat (Local container) | Celery Beat (Volume-backed state) | Redundant Celery Beat with Redis Lock |
| **Relational Database** | PostgreSQL 16 (Local Container) | Managed Supabase / Neon PostgreSQL 16 (SSL) | AWS Aurora PostgreSQL (Multi-AZ, Read Replicas) |
| **Cache & Queue Broker** | Redis 7 (Local Container) | Managed Upstash Redis 7 (TLS) | AWS ElastiCache for Redis (Cluster Mode) |
| **Object / Media Storage**| Local `./tmp` directory | Cloudinary Media CDN | AWS S3 / Cloudflare R2 + Cloudinary |
| **ML Artifact Storage** | Local `./models` directory | Named Docker Volumes on Host | AWS S3 Bucket + Versioned Model Registry |
| **CI / CD Pipeline** | Local Git / Manual execution | GitHub Actions (Self-Hosted Runner on EC2) | GitHub Actions CI/CD with Staging & Canary Gates |

---

## 3. Current Production Infrastructure Diagram

```mermaid
flowchart TB
    subgraph Internet["Public Internet"]
        Users["Web & Mobile Users"]
        GH["GitHub Actions Trigger"]
    end

    subgraph AWSCloud["AWS Cloud Infrastructure"]
        subgraph EC2Instance["AWS EC2 Instance (Self-Hosted Runner & Docker Host)"]
            NginxIngress["Nginx / Port 80/443 (TLS Ingress)"]
            
            subgraph DockerStack["Docker Compose Production Stack"]
                MigrateJob["basarat-migrate (Alembic)"]
                APIApp["basarat-api (Uvicorn :8000)"]
                Worker["basarat-celery-worker"]
                Beat["basarat-celery-beat"]
            end
            
            subgraph HostStorage["Host Storage Volumes"]
                ParquetVol["OHLCV Parquet Volume"]
                ModelVol["Trained Model Weights"]
                BeatVol["Celery Beat State"]
            end
        end
    end

    subgraph ManagedSaaS["Managed Cloud Data & Services"]
        NeonDB[(Managed PostgreSQL 16 Pooler)]
        UpstashRedis[(Managed Upstash Redis 7 TLS)]
        GroqAPI["Groq Cloud LLM API"]
        HFAPI["HuggingFace FinBERT API"]
        SendGridAPI["SendGrid SMTP Service"]
        CloudinaryCDN["Cloudinary Media Storage"]
    end

    Users <-->|HTTPS / WSS| NginxIngress
    NginxIngress <-->|Proxy Pass :8000| APIApp
    GH -->|Self-Hosted Runner Deploy| EC2Instance

    APIApp <-->|Async Queries (Port 5432/6543 SSL)| NeonDB
    APIApp <-->|Cache & PubSub Bus| UpstashRedis
    Worker <-->|Task Broker & Backend| UpstashRedis
    Worker -->|Sync Queries| NeonDB
    Beat -->|Publish Crons| UpstashRedis

    APIApp --> GroqAPI
    Worker --> HFAPI
    Worker --> SendGridAPI
    APIApp --> CloudinaryCDN

    APIApp --- ParquetVol
    Worker --- ParquetVol
    Worker --- ModelVol
    Beat --- BeatVol
```

---

## 4. Hardware & Resource Sizing

### Current Production Host Specifications (AWS EC2):
- **Instance Type:** `t3.large` or `c6i.large` (2 vCPUs, 8 GB RAM, 50 GB gp3 SSD).
- **CPU Allocation:**
  - `basarat-api`: 0.75 vCPU
  - `basarat-celery-worker`: 0.75 vCPU
  - `basarat-celery-beat`: 0.10 vCPU
  - System & Ingress: 0.40 vCPU
- **Memory Allocation:**
  - `basarat-api`: ~800 MB (TensorFlow/XGBoost models in memory)
  - `basarat-celery-worker`: ~1.5 GB (Pandas feature engineering and Monte Carlo)
  - `basarat-celery-beat`: ~150 MB
  - Ingress, OS & Runner: ~1.5 GB
  - Available Buffer: ~4.0 GB

---

## 5. Recommended Enterprise Scale-Out Architecture

For enterprise scaling (> 50,000 active concurrent users):

1. **Decouple API from Workers:** Split API web containers and Celery worker instances into separate AWS ECS task definitions.
2. **Horizontal Web Autoscaling:** Deploy behind an AWS Application Load Balancer (ALB) scaling from 2 to 10 Uvicorn tasks based on CPU/RAM utilization.
3. **Database Read Replicas:** Direct read-heavy analytics queries (`GET /market/quotes`, `GET /stocks/{symbol}/price-history`) to Aurora Read Replicas, reserving primary writer for portfolio transactions and user updates.
4. **Cloud Object Storage for ML Data:** Store `features_daily.parquet` and daily OHLCV files in Amazon S3 with S3fs mounting.
