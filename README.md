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

## 🏥 Monitoramento

### Health Checks
```bash
# Liveness
curl http://localhost:8000/health/live

# Readiness (com dependências)
curl http://localhost:8000/health/ready
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
