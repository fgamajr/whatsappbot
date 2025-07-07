# Sistema de Prompts Dinâmicos

## Visão Geral

O sistema agora suporta **prompts gerenciáveis no banco de dados** ao invés do prompt hardcoded. Os usuários podem escolher diferentes tipos de análise e o sistema lembra suas preferências.

## Funcionalidades

### 🎯 **Tipos de Análise Disponíveis**

1. **🎯 Análise Completa de Entrevista** (`entrevista`)
   - Análise abrangente incluindo experiência, personalidade, pontos fortes e adequação cultural
   - O prompt original migrado para o banco

2. **⚡ Resumo Rápido** (`resumo`)
   - Resumo conciso com pontos principais da entrevista
   - Máximo 500 palavras, foco nos highlights

3. **🔧 Foco em Habilidades Técnicas** (`tecnico`)
   - Análise detalhada das competências técnicas e experiência profissional
   - Ideal para avaliações de desenvolvedores/técnicos

4. **🤝 Análise de Fit Cultural** (`cultura`)
   - Foco em valores, motivações e adequação à cultura organizacional
   - Perfeito para avaliar alinhamento cultural

5. **🎨 Análise Personalizada** (`custom`)
   - Prompt flexível para análises específicas
   - Requer variável `{custom_instructions}`

## Interface do Usuário

### **Comandos Disponíveis**

```
prompts          - Ver tipos de análise disponíveis
help             - Ajuda completa do sistema
status           - Status do sistema
padrão           - Usar análise mais popular
```

### **Seleção de Prompts**

Os usuários podem escolher prompts de 3 formas:

1. **Por número:** `1`, `2`, `3`, `4`
2. **Por código:** `entrevista`, `resumo`, `tecnico`, `cultura`
3. **Padrão:** `padrão` (usa o mais popular)

### **Fluxo de Uso**

```
👤 Usuário: prompts

🤖 Bot: 📝 Escolha o tipo de análise:

1️⃣ 🎯 Análise Completa de Entrevista
   Análise abrangente incluindo experiência...

2️⃣ ⚡ Resumo Rápido
   Resumo conciso com pontos principais...

💡 Como escolher:
• Digite o número (ex: 1)
• Digite o código (ex: resumo)

👤 Usuário: 2

🤖 Bot: ✅ Análise selecionada: ⚡ Resumo Rápido
Agora envie seu áudio para processamento!

👤 Usuário: [envia áudio]

🤖 Bot: [processa com o prompt selecionado]
```

## Arquitetura Técnica

### **Componentes Principais**

1. **Domain Entities (`app/domain/entities/prompt.py`)**
   - `PromptTemplate`: Entidade principal para templates
   - `UserPromptPreference`: Preferências do usuário
   - Enums para categoria e status

2. **Repository (`app/infrastructure/database/repositories/prompt.py`)**
   - CRUD completo para prompts
   - Busca por categoria, código, popularidade
   - Gestão de preferências do usuário

3. **Service (`app/services/prompt_manager.py`)**
   - Lógica de negócio para gestão de prompts
   - Interface para seleção do usuário
   - Formatação de menus e mensagens

4. **Integration**
   - `AnalysisService`: Atualizado para usar prompts dinâmicos
   - `MessageHandler`: Integrado com seleção de usuário
   - API endpoints: Comandos de texto para seleção

### **Banco de Dados**

**Collections:**
- `prompts`: Templates de prompts
- `user_prompt_preferences`: Preferências dos usuários

**Campos Principais:**
```javascript
{
  id: "uuid-timestamp",
  name: "Análise Completa de Entrevista",
  short_code: "entrevista",
  category: "interview_analysis", 
  status: "active",
  prompt_text: "Com base APENAS na transcrição...",
  usage_count: 42,
  emoji: "🎯"
}
```

## Gerenciamento de Prompts

### **Script de Setup**

```bash
# Criar prompts iniciais
python scripts/setup_prompts.py --create

# Listar prompts existentes
python scripts/setup_prompts.py --list
```

### **Adicionando Novos Prompts**

Para adicionar novos tipos de análise:

1. Criar o `PromptTemplate` no script ou via API
2. Definir categoria, código curto e emoji
3. Configurar ordem de exibição
4. Ativar no sistema

### **Métricas e Tracking**

- **Usage count**: Quantas vezes cada prompt foi usado
- **User preferences**: Prompt padrão e último usado por usuário  
- **Popular prompts**: Ranking por uso
- **Performance**: Timing de geração por prompt

## Benefícios

1. **Flexibilidade**: Diferentes tipos de análise para diferentes necessidades
2. **Personalização**: Usuários podem escolher o estilo preferido
3. **Escalabilidade**: Fácil adicionar novos tipos sem código
4. **Analytics**: Tracking de uso e preferências
5. **Manutenibilidade**: Prompts gerenciados no banco vs hardcoded

## Backward Compatibility

O sistema mantém compatibilidade total:
- Usuários que não selecionam prompts usam o padrão
- Análise existente continua funcionando normalmente
- Prompts antigos migrados automaticamente