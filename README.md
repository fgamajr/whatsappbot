# 🎙️ WhatsApp Interview Bot - Enterprise Edition

Sistema profissional de transcrição e análise de entrevistas via WhatsApp com arquitetura distribuída e processamento assíncrono avançado.

## 🚀 Características Principais

- **Arquitetura Enterprise**: Clean Architecture + DDD + Microservices
- **Processamento Assíncrono**: Celery + Redis com auto-scaling inteligente
- **AI Stack Especializada**: Whisper (transcrição) + Gemini (análise)
- **MongoDB Atlas**: Database cloud com backup automático e disaster recovery
- **Monitoramento Avançado**: Prometheus + Grafana + Business Metrics + SLA Monitoring
- **Segurança Enterprise**: HMAC verification, circuit breakers, secrets management
- **Export Multi-formato**: DOCX, PDF, TXT, JSON, CSV, XLSX, ZIP
- **Production Ready**: Docker, Kubernetes, health checks, alerting system

## 🏗️ Arquitetura Distribuída

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│    FastAPI App      │    │   Celery Workers    │    │   Monitoring Stack  │
│  ┌───────────────┐  │    │  ┌───────────────┐  │    │  ┌───────────────┐  │
│  │ Webhook API   │  │    │  │ Audio Worker  │  │    │  │ Prometheus    │  │
│  │ Health Checks │  │    │  │ AI Worker     │  │    │  │ Grafana       │  │
│  │ Export API    │  │    │  │ Export Worker │  │    │  │ Alerting      │  │
│  └───────────────┘  │    │  └───────────────┘  │    │  └───────────────┘  │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
         │                          │                          │
         └──────────────┬───────────────────────┬──────────────┘
                        │                       │
            ┌─────────────────────┐    ┌─────────────────────┐
            │    Redis Cluster    │    │   MongoDB Atlas     │
            │  ┌───────────────┐  │    │  ┌───────────────┐  │
            │  │ Task Queues   │  │    │  │ Interviews    │  │
            │  │ Rate Limiting │  │    │  │ Users         │  │
            │  │ Cache         │  │    │  │ Analytics     │  │
            │  │ Sessions      │  │    │  │ Backups       │  │
            │  └───────────────┘  │    │  └───────────────┘  │
            └─────────────────────┘    └─────────────────────┘
```

### Estrutura do Código

```
app/
├── main.py                           # FastAPI setup + circuit breakers
├── api/
│   ├── v1/                          # Controllers + health checks
│   ├── middleware/                  # Security + rate limiting
│   └── endpoints/                   # Monitoring + export APIs
├── domain/                          # Entidades e regras de negócio
├── services/                        # Lógica de aplicação
├── infrastructure/
│   ├── ai/                         # Whisper + Gemini clients
│   ├── messaging/                  # WhatsApp + Telegram
│   ├── database/                   # MongoDB + migrations
│   ├── redis/                      # Redis client + queues
│   ├── celery/                     # Task workers + routing
│   ├── monitoring/                 # Prometheus + business metrics
│   ├── security/                   # Secrets manager + validation
│   ├── patterns/                   # Circuit breaker + retry
│   └── disaster_recovery/          # Backup + recovery plans
├── tasks/                          # Celery task definitions
├── core/                           # Configuração e utilitários
└── prompts/                        # Prompts de IA otimizados
```

## 🛠️ Setup Rápido

### 1. Pré-requisitos
```bash
# Docker e Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Python 3.11+ (desenvolvimento local)
sudo apt update && sudo apt install python3.11 python3.11-venv
```

### 2. Instalação Completa
```bash
# Clone o repositório
git clone <repository>
cd whatsappbot

# Executar setup automático
chmod +x scripts/setup.sh
./scripts/setup.sh

# Configurar variáveis de ambiente
cp .env.example .env
# Edite .env com suas credenciais (veja seção de configuração)
```

### 3. Configuração Obrigatória

#### Variáveis Essenciais (.env)
```bash
# WhatsApp Business API
WHATSAPP_TOKEN=your_permanent_token
WHATSAPP_VERIFY_TOKEN=your_verify_token  
PHONE_NUMBER_ID=your_phone_number_id
WHATSAPP_WEBHOOK_SECRET=your_webhook_secret

# OpenAI (Whisper)
OPENAI_API_KEY=sk-...

# Google Gemini
GEMINI_API_KEY=your_gemini_key

# MongoDB Atlas
MONGODB_URL=mongodb+srv://username:password@cluster.mongodb.net/database

# Redis (opcional para desenvolvimento, obrigatório para produção)
REDIS_URL=redis://localhost:6379

# Ambiente
ENVIRONMENT=development  # ou production
DEBUG=true              # false em produção
VERSION=2.0.0
```

#### Configurações Opcionais de Monitoramento
```bash
# Email Alertas
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
ALERT_EMAIL=admin@yourcompany.com

# Slack Alertas
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...

# S3 Backup (opcional)
BACKUP_S3_BUCKET=your-backup-bucket
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key

# Telegram (opcional)
TELEGRAM_BOT_TOKEN=your_telegram_token
TELEGRAM_WEBHOOK_SECRET=your_telegram_secret
```

### 4. Execução

#### Desenvolvimento Local
```bash
# Desenvolvimento simples (sem Celery)
./scripts/run.sh dev

# Desenvolvimento completo (com Celery + Redis)
./scripts/run.sh dev-full

# Logs em tempo real
./scripts/logs.sh
```

#### Produção
```bash
# Docker Compose (recomendado)
docker-compose -f docker-compose.celery.yml up -d

# Verificar status
docker-compose -f docker-compose.celery.yml ps

# Logs
docker-compose -f docker-compose.celery.yml logs -f
```

## 📦 Funcionalidades Avançadas

### 🎵 Processamento de Áudio Paralelo
- **Pipeline Assíncrono**: Segmentação → Transcrição → Análise em paralelo
- **Performance**: 41% mais rápido que processamento sequencial
- **Suporte**: Qualquer duração de áudio (chunks automáticos de 15min)
- **Formatos**: Conversão automática para MP3 otimizado
- **Progress**: Updates em tempo real via WebSocket

### 🎙️ Transcrição Avançada (Whisper)
- **Multi-Worker**: Processamento paralelo de segmentos
- **Timestamps**: Precisão em milissegundos
- **Speaker Diarization**: Identificação de locutores
- **Idioma**: Português brasileiro otimizado
- **Retry Logic**: Circuit breaker + retry automático

### 🧠 Análise Inteligente (Gemini)
- **Prompts Especializados**: Otimizados para entrevistas brasileiras
- **Análise Multi-dimensional**:
  - Avaliação Técnica e Profissional
  - Perfil Comportamental e Soft Skills
  - Motivações e Fit Cultural
  - Pontos Fortes e Desenvolvimento
- **Structured Output**: JSON estruturado para integração

### 📄 Export Multi-formato
- **Formatos Suportados**: DOCX, PDF, TXT, JSON, CSV, XLSX, ZIP
- **Templates Profissionais**: Formatação automática
- **Batch Export**: Múltiplos formatos simultaneamente
- **API Endpoints**: `/export/{interview_id}/{format}`
- **Async Processing**: Export em background para arquivos grandes

### 🔄 Sistema de Filas Avançado

#### Workers Especializados
```bash
# Audio Worker - Processamento de áudio
celery -A app.celery_app worker -Q audio_processing -n audio_worker@%h --concurrency=2

# AI Worker - Transcrição e análise
celery -A app.celery_app worker -Q ai_processing -n ai_worker@%h --concurrency=4

# Export Worker - Geração de documentos
celery -A app.celery_app worker -Q export_processing -n export_worker@%h --concurrency=3

# General Worker - Tarefas gerais
celery -A app.celery_app worker -Q general -n general_worker@%h --concurrency=2
```

#### Auto-scaling Inteligente
- **Baseado em Métricas**: Tamanho da fila + tempo de resposta
- **Scaling Policies**: Automático com Docker Compose, Kubernetes, Fly.io
- **Thresholds**: Configuráveis por ambiente
- **Cool-down Periods**: Previne oscillações

## 🏥 Monitoramento Enterprise

### Health Checks Avançados
```bash
# Liveness (básico)
curl http://localhost:8000/health/live

# Readiness (completo com dependências)
curl http://localhost:8000/health/ready

# Deep Health Check (end-to-end)
curl http://localhost:8000/health/deep
```

### Business Metrics e SLAs
- **KPIs Principais**:
  - Taxa de Sucesso das Entrevistas: >95%
  - Tempo de Processamento: <30min para áudios de 60min
  - Disponibilidade da API: >99.5%
  - Taxa de Erro: <2%
  - Satisfação do Usuário: >4.0/5.0

### Alerting Inteligente
- **Canais**: Email, Slack, WebSocket, SMS, Webhook
- **Severidades**: INFO, WARNING, CRITICAL, EMERGENCY
- **Cooldown**: Evita spam de alertas
- **Auto-Resolution**: Notificação quando problemas são resolvidos

### Dashboards Prometheus + Grafana
```bash
# Prometheus (métricas)
http://localhost:9090

# Grafana (dashboards)
http://localhost:3000
```

**Dashboards Disponíveis**:
- System Overview (CPU, Memory, Disk, Network)
- Application Metrics (Requests, Response Times, Errors)
- Business KPIs (Interviews, Success Rate, Processing Time)
- Celery Monitoring (Queue Length, Worker Status, Task Duration)
- Redis Performance (Connections, Memory, Commands)
- MongoDB Performance (Operations, Response Time, Storage)

## 🔒 Segurança Enterprise

### Webhook Security
```python
# HMAC-SHA256 verification
WHATSAPP_WEBHOOK_SECRET=your_secret_key
TELEGRAM_WEBHOOK_SECRET=your_secret_key
```

### Input Validation & Sanitization
- **Audio Files**: Formato, tamanho, duration validation
- **Text Input**: Sanitização contra XSS/injection
- **Rate Limiting**: 100 requests/minute por usuário
- **File Upload**: Antivirus scanning (opcional)

### Circuit Breaker Pattern
- **External APIs**: OpenAI, Gemini, WhatsApp
- **Automatic Recovery**: Self-healing quando serviços voltam
- **Fallback Strategies**: Respostas alternativas quando APIs falham

### Secrets Management
- **Environment Variables**: Nunca commitados
- **Rotation Support**: Rotação automática de secrets
- **Encryption**: Secrets em repouso criptografados
- **Audit Trail**: Log de acesso a secrets

### Secure Logging
- **Structured Logs**: JSON format
- **No Sensitive Data**: PII e secrets automaticamente mascarados
- **Audit Trail**: Log de todas as operações importantes
- **Log Retention**: Configurável por compliance

## 🚀 Deploy Produção

### Docker Compose (Recomendado)
```bash
# Build e deploy
docker-compose -f docker-compose.celery.yml up -d

# Scaling manual
docker-compose -f docker-compose.celery.yml up -d --scale ai_worker=3 --scale audio_worker=2

# Monitoring
docker-compose -f docker-compose.celery.yml logs -f app
```

### Kubernetes
```yaml
# k8s/deployment.yaml (exemplo)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: interview-bot
spec:
  replicas: 3
  selector:
    matchLabels:
      app: interview-bot
  template:
    metadata:
      labels:
        app: interview-bot
    spec:
      containers:
      - name: app
        image: interview-bot:latest
        ports:
        - containerPort: 8000
        env:
        - name: ENVIRONMENT
          value: "production"
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
```

### Fly.io
```bash
# Deploy
fly deploy

# Scaling
fly scale count 3

# Secrets
fly secrets set OPENAI_API_KEY=sk-...
```

## 📊 Performance Benchmarks

| Métrica | Valor Atual | Target SLA |
|---------|-------------|------------|
| Webhook Response | <500ms | <1s |
| Audio 15min | ~2-3min | <5min |
| Audio 60min | ~8-12min | <20min |
| Concurrent Interviews | 20+ | 50+ |
| API Availability | 99.8% | 99.5% |
| Error Rate | <1% | <2% |
| P95 Response Time | <2s | <5s |

### Otimizações Implementadas
- **Pipeline Paralelo**: 41% faster processing
- **Connection Pooling**: MongoDB + Redis
- **Caching Strategy**: Redis para resultados frequentes
- **Async Processing**: Celery para operações pesadas
- **Resource Limits**: Containers com limits apropriados

## 🧪 Testes e Quality Assurance

### Executar Testes
```bash
# Todos os testes
./scripts/test.sh

# Apenas unitários
pytest tests/unit/ -v

# Apenas integração
pytest tests/integration/ -v

# Com coverage
pytest --cov=app --cov-report=html tests/

# Performance tests
pytest tests/performance/ -v
```

### CI/CD Pipeline
```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      mongodb:
        image: mongo:7
      redis:
        image: redis:7
    steps:
    - uses: actions/checkout@v3
    - name: Run tests
      run: |
        pip install -r requirements.txt
        pytest --cov=app tests/
```

## 🔧 Comandos e APIs

### Bot Commands
| Comando | Função |
|---------|--------|
| `help` | Manual completo do bot |
| `status` | Status do sistema e filas |
| `/completo` | Modo com identificação de locutores |
| `/simples` | Modo sem locutores (mais rápido) |
| `/cancel` | Cancelar processamento atual |
| `/history` | Histórico de entrevistas |

### REST API Endpoints

#### Core APIs
```bash
# Health & Status
GET /health/live
GET /health/ready  
GET /health/deep

# Webhook
POST /webhook/whatsapp
POST /webhook/telegram

# Export
GET /export/{interview_id}/docx
GET /export/{interview_id}/pdf
GET /export/{interview_id}/json
POST /export/batch
```

#### Monitoring APIs
```bash
# System Metrics
GET /metrics/system
GET /metrics/business
GET /metrics/prometheus

# Auto-scaling
GET /scaling/status
POST /scaling/manual/{component}/{replicas}

# Disaster Recovery
GET /recovery/status
POST /recovery/backup
POST /recovery/restore/{backup_id}
```

#### Admin APIs (Development)
```bash
# Celery Management
GET /celery/status
POST /celery/purge/{queue}
POST /celery/test/{task}

# Alerting
GET /alerts/status
POST /alerts/test/{rule_name}
POST /alerts/rules

# Capacity Planning
GET /capacity/forecast
GET /capacity/recommendations
```

## 🔄 Disaster Recovery

### Backup Automático
- **Agendamento**: Daily backups às 2:00 AM UTC
- **Componentes**: MongoDB + Redis + Configuration
- **Retenção**: 30 dias (configurável)
- **Storage**: Local + S3 (opcional)
- **Compressão**: tar.gz com até 90% de compactação

### Recovery Plans
```bash
# Backup manual
curl -X POST http://localhost:8000/recovery/backup

# Recovery completo
curl -X POST http://localhost:8000/recovery/restore/backup_20241204_140000

# Recovery apenas database
curl -X POST http://localhost:8000/recovery/restore/backup_20241204_140000 \
  -H "Content-Type: application/json" \
  -d '{"type": "database_only"}'
```

### RTO/RPO Targets
- **RTO** (Recovery Time Objective): 30 minutos
- **RPO** (Recovery Point Objective): 15 minutos
- **Data Loss Window**: Máximo 5 minutos para dados críticos

## 📈 Capacity Planning

### ML-based Forecasting
- **Algoritmo**: Polynomial regression com diferentes graus
- **Métricas**: CPU, Memory, Queue Length, Daily Interviews
- **Horizonte**: 30 dias de previsão
- **Confidence Interval**: 95% statistical confidence
- **Recommendations**: Scaling actions baseadas em trends

### Auto-scaling Triggers
```yaml
# Scaling Rules
cpu_threshold: 70%
memory_threshold: 80%
queue_length_threshold: 100
response_time_threshold: 5000ms

# Scaling Actions
scale_up_cooldown: 300s
scale_down_cooldown: 600s
min_replicas: 1
max_replicas: 10
```

## 🐛 Troubleshooting

### Problemas Comuns

#### 1. Webhook não responde
```bash
# Verificar logs
docker-compose logs -f app

# Verificar health
curl http://localhost:8000/health/ready

# Verificar rate limiting
curl http://localhost:8000/metrics/system | grep rate_limit

# Verificar webhook signature
# Validar WHATSAPP_WEBHOOK_SECRET no .env
```

#### 2. Celery workers não processam
```bash
# Verificar workers ativos
docker-compose exec app celery -A app.celery_app inspect active

# Verificar queues
docker-compose exec app celery -A app.celery_app inspect active_queues

# Verificar Redis connection
docker-compose exec redis redis-cli ping

# Restart workers
docker-compose restart audio_worker ai_worker
```

#### 3. Transcrição falha
```bash
# Verificar quota OpenAI
curl https://api.openai.com/v1/usage \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# Verificar logs específicos
docker-compose logs -f ai_worker | grep whisper

# Verificar circuit breaker
curl http://localhost:8000/metrics/system | grep circuit_breaker
```

#### 4. MongoDB connection issues
```bash
# Verificar connection string
echo $MONGODB_URL

# Test connection
docker-compose exec app python -c "
from app.infrastructure.database.mongodb import MongoDB
import asyncio
async def test():
    await MongoDB.connect()
    print('MongoDB OK')
asyncio.run(test())
"

# Verificar IP whitelist no Atlas
# Adicionar IP atual: 0.0.0.0/0 (desenvolvimento)
```

#### 5. High memory usage
```bash
# Verificar usage por container
docker stats

# Ajustar worker concurrency
# Editar docker-compose.celery.yml:
# --concurrency=2 (reduzir se necessário)

# Verificar memory leaks
docker-compose exec app python -c "
import psutil, gc
gc.collect()
print(f'Memory: {psutil.virtual_memory().percent}%')
"
```

### Performance Debugging
```bash
# Slow queries MongoDB
docker-compose exec mongodb mongosh --eval "
db.setProfilingLevel(2)
db.system.profile.find().limit(5).sort({ts:-1}).pretty()
"

# Redis slow log
docker-compose exec redis redis-cli slowlog get 10

# Celery task profiling
docker-compose exec app celery -A app.celery_app events
```

### Monitoring Alerts
```bash
# Check active alerts
curl http://localhost:8000/alerts/status

# Test alert (development)
curl -X POST http://localhost:8000/alerts/test/error_rate_critical

# Check business metrics
curl http://localhost:8000/metrics/business
```

## 🤝 Contribuição

### Development Workflow
```bash
# 1. Fork e clone
git clone <your-fork>
cd whatsappbot

# 2. Criar branch
git checkout -b feature/nova-funcionalidade

# 3. Development local
./scripts/run.sh dev-full

# 4. Testes
./scripts/test.sh

# 5. Commit com conventional commits
git commit -m "feat: adiciona export em PDF"

# 6. Push e PR
git push origin feature/nova-funcionalidade
```

### Code Standards
- **Python**: PEP 8 + Black + isort
- **Architecture**: Clean Architecture + DDD
- **Tests**: Pytest com 80%+ coverage
- **Documentation**: Docstrings + type hints
- **Commits**: Conventional Commits

### Testing Guidelines
```bash
# Unit tests
pytest tests/unit/ -v --cov=app

# Integration tests (requer Docker)
pytest tests/integration/ -v

# E2E tests
pytest tests/e2e/ -v

# Performance tests
pytest tests/performance/ -v --benchmark-only
```

## 📄 Licença

MIT License - veja [LICENSE](LICENSE) para detalhes.

## 🔗 Links e Documentação

### APIs Externas
- [WhatsApp Business API](https://developers.facebook.com/docs/whatsapp)
- [OpenAI Whisper API](https://platform.openai.com/docs/guides/speech-to-text)
- [Google Gemini API](https://ai.google.dev/docs)
- [Telegram Bot API](https://core.telegram.org/bots/api)

### Infraestrutura
- [MongoDB Atlas](https://www.mongodb.com/atlas)
- [Redis Documentation](https://redis.io/documentation)
- [Celery Documentation](https://docs.celeryproject.org/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

### Monitoring & Observability
- [Prometheus](https://prometheus.io/docs/)
- [Grafana](https://grafana.com/docs/)
- [OpenTelemetry](https://opentelemetry.io/docs/)

### Deployment
- [Docker Compose](https://docs.docker.com/compose/)
- [Kubernetes](https://kubernetes.io/docs/)
- [Fly.io](https://fly.io/docs/)

---

## 📊 System Architecture Summary

### Current Implementation Status

✅ **Phase 1 - Core Infrastructure** (Completed)
- Clean Architecture + DDD
- FastAPI + MongoDB + Redis
- Basic Celery integration
- Security (HMAC verification, input validation)
- Health checks and monitoring

✅ **Phase 2 - Distributed Processing** (Completed) 
- Parallel audio processing pipeline (41% performance improvement)
- Specialized Celery workers (audio, AI, export, general)
- Intelligent task routing
- WebSocket real-time updates

✅ **Phase 3 - Production Optimization** (Completed)
- Auto-scaling system (Docker Compose + Kubernetes + Fly.io)
- Advanced monitoring (Prometheus + Grafana + Business Metrics)
- SLA monitoring and alerting system
- Export system (7 formats: DOCX, PDF, TXT, JSON, CSV, XLSX, ZIP)

✅ **Phase 4 - Enterprise Components** (Completed)
- Circuit breaker pattern for external APIs
- Comprehensive secrets management with rotation
- Business metrics with SLA monitoring and intelligent alerting
- Disaster recovery with automated backup and S3 integration
- Deep health checks with functional and performance testing
- ML-based capacity planning with forecasting and cost analysis

### Architecture Highlights

🏗️ **Distributed Architecture**
- Microservices pattern with specialized workers
- Async processing with Celery + Redis
- Circuit breaker protection for external APIs
- Auto-scaling based on queue metrics and performance

🔒 **Enterprise Security**
- HMAC-SHA256 webhook verification
- Input sanitization and validation
- Secure secrets management with encryption
- Rate limiting and circuit breaker patterns
- Secure logging without sensitive data exposure

📊 **Advanced Monitoring**
- Business KPIs and SLA monitoring
- Real-time alerting across multiple channels (Email, Slack, WebSocket)
- Prometheus metrics + Grafana dashboards
- ML-based capacity planning and forecasting
- Deep health checks with end-to-end testing

🔄 **Disaster Recovery**
- Automated daily backups (MongoDB + Redis + Configuration)
- S3 integration for off-site backup storage
- Multiple recovery plans (full, database-only, redis-only)
- 30-minute RTO, 15-minute RPO targets

🚀 **Production Ready**
- Docker Compose for easy deployment
- Kubernetes manifests for enterprise scaling
- Fly.io support for modern cloud deployment
- Comprehensive testing suite (unit, integration, e2e, performance)
- CI/CD pipeline with automated testing

---

🚀 **Enterprise-grade WhatsApp Interview Bot com arquitetura distribuída, processamento assíncrono avançado, e monitoramento completo para produção!**