# 🎙️ WhatsApp Interview Bot - Enterprise Edition

Sistema profissional de transcrição e análise de entrevistas via WhatsApp com arquitetura limpa e processamento em background.

## 🚀 Características

- **Arquitetura Limpa**: Separação clara de responsabilidades (Clean Architecture + DDD)
- **Processamento Background**: Resposta imediata (<1s) + processamento assíncrono
- **AI Stack Especializada**: Whisper (transcrição) + Gemini (análise)
- **MongoDB Atlas**: Database cloud gerenciado com backup automático
- **Production Ready**: Docker, health checks, monitoring, logs estruturados

## 🏗️ Arquitetura

```
app/
├── main.py                    # FastAPI setup (50 linhas!)
├── api/v1/                   # Controllers
├── domain/                   # Entidades e regras de negócio
├── services/                 # Lógica de aplicação
├── infrastructure/           # Integrações externas
├── core/                     # Configuração e utilitários
└── prompts/                  # Prompts de IA
```

## 🛠️ Setup Rápido

### 1. Instalação
```bash
# Executar o script de setup
./scripts/setup.sh

# Editar variáveis de ambiente
cp .env.example .env
# Edite o .env com suas credenciais
```

### 2. Configuração Obrigatória

```bash
# .env
WHATSAPP_TOKEN=your_token
WHATSAPP_VERIFY_TOKEN=your_verify_token
PHONE_NUMBER_ID=your_phone_id
OPENAI_API_KEY=your_openai_key
GEMINI_API_KEY=your_gemini_key
MONGODB_URL=mongodb+srv://...
```

### 3. Execução

```bash
# Desenvolvimento
./scripts/run.sh dev

# Produção
./scripts/run.sh

# Docker
docker-compose up -d
```

## 📦 Funcionalidades

### 🎵 Processamento de Áudio
- **Suporte**: Qualquer duração de áudio
- **Chunks**: Divisão automática em segmentos de 15min
- **Formatos**: Conversão automática para MP3
- **Progress**: Updates em tempo real

### 🎬 **YouTube Downloading (Resilient System)**
- **Auto-Updates**: yt-dlp mantido sempre atualizado
- **Fault Tolerance**: Sistema resiliente a mudanças do YouTube
- **Microservice Architecture**: Serviço isolado e escalável
- **Progress Tracking**: Updates em tempo real do download
- **Format Intelligence**: Seleção automática do melhor formato
- **Size Control**: Limites configuráveis de duração e tamanho

### 🎙️ Transcrição (Whisper)
- **Timestamps**: Precisão em milissegundos
- **Idioma**: Português otimizado
- **Modos**: 
  - Completo (com identificação de locutores)
  - Simples (apenas timestamps)

### 🧠 Análise (Gemini)
- **Avaliação Profissional**: Experiência e conquistas
- **Perfil Pessoal**: Motivações e valores
- **Análise Comportamental**: Soft skills e liderança
- **Recomendações**: Pontos fortes e desenvolvimento

### 📄 Documentos
- **Transcrição**: DOCX com timestamps formatados
- **Análise**: DOCX estruturado com insights
- **Entrega**: Via WhatsApp automaticamente

## 🔧 Comandos do Bot

| Comando | Função |
|---------|--------|
| `help` | Manual completo |
| `status` | Status do sistema |
| `/completo` | Modo com locutores |
| `/simples` | Modo sem locutores |
| **YouTube URLs** | Download automático + processamento |
| `Sim`/`Não` | Confirmação de processamento de vídeo |

## 🎬 Sistema Resiliente de YouTube

### 🛠️ Arquitetura

O sistema de download do YouTube foi projetado para ser **resiliente às mudanças constantes do YouTube**, que frequentemente altera seus métodos de assinatura e quebra ferramentas como yt-dlp.

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Main App      │    │  yt-dlp Service │    │   Auto-Updater  │
│                 │ ──▶│                 │ ──▶│                 │
│ Resilient Client│    │ Docker Container│    │  Cron + Health  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### ⚙️ Setup do Sistema YouTube

```bash
# 1. Deploy completo do sistema YouTube
./scripts/setup-youtube.sh

# 2. Verificar status
./scripts/youtube-status.sh

# 3. Atualizar manualmente (se necessário)
./scripts/youtube-update.sh
```

### 🔄 Como Funciona

1. **Detecção**: URLs do YouTube são detectadas automaticamente
2. **Download**: Serviço isolado faz o download usando yt-dlp atualizado
3. **Entrega**: Vídeo/áudio é enviado para o usuário
4. **Confirmação**: Usuário confirma se quer processar
5. **Processamento**: Transcrição + análise como áudio normal

### 🛡️ Características de Resilência

- **Auto-Updates**: yt-dlp atualizado a cada 6 horas
- **Health Checks**: Verificação de saúde a cada 30 minutos
- **Retry Logic**: 3 tentativas com backoff exponencial
- **Isolation**: Falhas não afetam o app principal
- **Monitoring**: Logs estruturados e alertas
- **Fallbacks**: Múltiplas estratégias de download

### 📊 Configurações YouTube

```bash
# .env - Configurações do sistema YouTube
YTDLP_SERVICE_URL=http://localhost:8080
YTDLP_AUTO_UPDATE=true
YTDLP_UPDATE_INTERVAL_HOURS=6

# Limites de download
YOUTUBE_MAX_DURATION=7200        # 2 horas
YOUTUBE_MAX_FILE_SIZE=209715200  # 200MB
YOUTUBE_QUALITY="best[ext=mp4][height<=720]/best"
```

### 🔧 Comandos YouTube

```bash
# Gerenciamento do serviço
./scripts/youtube-start.sh    # Iniciar serviço
./scripts/youtube-stop.sh     # Parar serviço
./scripts/youtube-restart.sh  # Reiniciar serviço
./scripts/youtube-logs.sh     # Ver logs
./scripts/youtube-update.sh   # Atualizar yt-dlp

# Monitoramento
./scripts/youtube-health.sh   # Check de saúde
./scripts/youtube-test.sh     # Teste funcional
./scripts/youtube-monitor.sh  # Monitor contínuo
```

### 🚨 Troubleshooting YouTube

```bash
# 1. Verificar status do serviço
./scripts/youtube-status.sh

# 2. Ver logs detalhados  
./scripts/youtube-logs.sh --follow

# 3. Testar download manual
./scripts/youtube-test.sh "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# 4. Forçar atualização
./scripts/youtube-update.sh --force

# 5. Reset completo
./scripts/youtube-reset.sh
```

## 🏥 Monitoramento

### Health Checks
```bash
# Liveness (app principal)
curl http://localhost:8000/health/live

# Readiness (com dependências)
curl http://localhost:8000/health/ready

# YouTube Service
curl http://localhost:8080/health
```

### Logs Estruturados
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "message": "Interview processing started",
  "interview_id": "abc123",
  "phone_number": "5511999887766"
}
```

## 🚀 Deploy Produção

### Docker
```bash
# Build
docker build -f docker/Dockerfile -t interview-bot .

# Run
docker-compose up -d
```

### Kubernetes (opcional)
```bash
# TODO: Adicionar manifests K8s
kubectl apply -f k8s/
```

## 🧪 Testes

```bash
# Executar todos os testes
./scripts/test.sh

# Apenas testes unitários
pytest tests/unit/

# Com coverage
pytest --cov=app tests/
```

## 📊 Performance

| Métrica | Valor |
|---------|-------|
| Webhook Response | <1s |
| Audio 15min | ~3-5min |
| Audio 60min | ~12-20min |
| Concurrent Users | 50+ |
| Uptime Target | 99.9% |

## 🔒 Segurança

- **Validação**: Input sanitization
- **Rate Limiting**: Anti-spam
- **Secrets**: Environment variables
- **HTTPS**: TLS obrigatório
- **Logs**: Sem dados sensíveis

## 📈 Escalabilidade

- **Horizontal**: Load balancer + múltiplas instâncias
- **Database**: MongoDB Atlas auto-scaling
- **Cache**: Redis (opcional)
- **Queue**: Background tasks assíncronas

## 🐛 Troubleshooting

### Problemas Comuns

1. **Webhook não responde**
   ```bash
   # Verificar logs
   docker logs interview-bot
   
   # Verificar health
   curl http://localhost:8000/health/ready
   ```

2. **Transcrição falha**
   ```bash
   # Verificar quota OpenAI
   # Verificar formato do áudio
   # Verificar logs do Whisper
   ```

3. **MongoDB connection**
   ```bash
   # Verificar connection string
   # Verificar IP whitelist no Atlas
   ```

## 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch: `git checkout -b feature/nova-funcionalidade`
3. Commit: `git commit -m 'Adiciona nova funcionalidade'`
4. Push: `git push origin feature/nova-funcionalidade`
5. Pull Request

## 📄 Licença

MIT License - veja [LICENSE](LICENSE) para detalhes.

## 🔗 Links Úteis

- [WhatsApp Business API](https://developers.facebook.com/docs/whatsapp)
- [OpenAI Whisper](https://openai.com/research/whisper)
- [Google Gemini](https://deepmind.google/technologies/gemini/)
- [MongoDB Atlas](https://www.mongodb.com/atlas)
- [FastAPI Docs](https://fastapi.tiangolo.com/)

---

🚀 **Feito com Clean Architecture para produção enterprise!**
