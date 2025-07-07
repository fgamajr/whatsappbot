#!/usr/bin/env python3
"""
Setup script to populate the database with initial prompt templates
"""
import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.domain.entities.prompt import PromptTemplate, PromptCategory, PromptStatus
from app.infrastructure.database.repositories.prompt import PromptRepository
from app.infrastructure.database.mongodb import MongoDB
from app.prompts.interview_analysis import INTERVIEW_ANALYSIS_PROMPT


async def create_initial_prompts():
    """Create initial prompt templates in the database"""
    
    # Connect to database
    await MongoDB.connect()
    
    prompt_repo = PromptRepository()
    
    # 1. Original Interview Analysis Prompt
    interview_prompt = PromptTemplate(
        name="Análise Completa de Entrevista",
        description="Análise abrangente incluindo experiência, personalidade, pontos fortes e adequação cultural",
        category=PromptCategory.INTERVIEW_ANALYSIS,
        status=PromptStatus.ACTIVE,
        prompt_text=INTERVIEW_ANALYSIS_PROMPT.strip(),
        variables=["transcript"],
        emoji="🎯",
        short_code="entrevista",
        tags=["entrevista", "análise", "completa", "detalhada"],
        display_order=1,
        settings={
            "max_tokens": 4000,
            "temperature": 0.7
        }
    )
    
    # 2. Quick Summary Prompt
    quick_summary_prompt = PromptTemplate(
        name="Resumo Rápido",
        description="Resumo conciso com pontos principais da entrevista",
        category=PromptCategory.INTERVIEW_ANALYSIS,
        status=PromptStatus.ACTIVE,
        prompt_text="""
Com base na transcrição da entrevista fornecida, crie um resumo CONCISO (máximo 500 palavras) em PORTUGUÊS que inclua:

1. **Perfil Profissional:**
   - Cargo/área de atuação atual
   - Experiência relevante principal
   - Principais habilidades técnicas mencionadas

2. **Destaques da Conversa:**
   - 2-3 pontos mais importantes da entrevista
   - Conquistas ou projetos relevantes mencionados
   - Aspectos únicos do candidato

3. **Impressão Geral:**
   - Avaliação resumida do perfil
   - Principal ponto forte identificado
   - Adequação geral para posições similares

Seja objetivo e direto. Base-se APENAS no que foi discutido na transcrição: {transcript}
        """.strip(),
        variables=["transcript"],
        emoji="⚡",
        short_code="resumo",
        tags=["resumo", "rápido", "conciso", "pontos principais"],
        display_order=2,
        settings={
            "max_tokens": 1500,
            "temperature": 0.5
        }
    )
    
    # 3. Technical Skills Focus
    technical_prompt = PromptTemplate(
        name="Foco em Habilidades Técnicas",
        description="Análise detalhada das competências técnicas e experiência profissional",
        category=PromptCategory.INTERVIEW_ANALYSIS,
        status=PromptStatus.ACTIVE,
        prompt_text="""
Analise a transcrição da entrevista focando especificamente nas HABILIDADES TÉCNICAS e EXPERIÊNCIA PROFISSIONAL. Responda em PORTUGUÊS:

1. **Competências Técnicas:**
   - Liste todas as tecnologias, ferramentas e linguagens mencionadas
   - Nível de experiência demonstrado (iniciante/intermediário/avançado)
   - Certificações ou cursos técnicos citados

2. **Experiência Prática:**
   - Projetos específicos descritos em detalhes
   - Responsabilidades técnicas em cargos anteriores
   - Problemas técnicos resolvidos ou desafios superados

3. **Metodologias e Processos:**
   - Metodologias de trabalho mencionadas (Agile, Scrum, etc.)
   - Ferramentas de gestão ou colaboração utilizadas
   - Práticas de desenvolvimento ou operacionais

4. **Evolução Técnica:**
   - Progressão na carreira técnica
   - Aprendizado contínuo e adaptação tecnológica
   - Capacidade de liderança técnica demonstrada

5. **Lacunas ou Áreas de Desenvolvimento:**
   - Tecnologias que gostaria de aprender
   - Áreas onde busca crescimento técnico

Base sua análise exclusivamente na transcrição: {transcript}
        """.strip(),
        variables=["transcript"],
        emoji="🔧",
        short_code="tecnico",
        tags=["técnico", "habilidades", "experiência", "tecnologia"],
        display_order=3,
        settings={
            "max_tokens": 3000,
            "temperature": 0.3
        }
    )
    
    # 4. Cultural Fit Analysis
    cultural_prompt = PromptTemplate(
        name="Análise de Fit Cultural",
        description="Foco em valores, motivações e adequação à cultura organizacional",
        category=PromptCategory.INTERVIEW_ANALYSIS,
        status=PromptStatus.ACTIVE,
        prompt_text="""
Analise a transcrição da entrevista com foco na ADEQUAÇÃO CULTURAL e MOTIVAÇÕES. Responda em PORTUGUÊS:

1. **Valores e Motivações:**
   - Valores pessoais e profissionais demonstrados
   - O que motiva o candidato no trabalho
   - Aspectos que mais valoriza em uma empresa

2. **Estilo de Trabalho:**
   - Preferência por trabalho individual vs. equipe
   - Como lida com pressão e deadlines
   - Abordagem para resolução de conflitos

3. **Comunicação e Relacionamento:**
   - Estilo de comunicação observado
   - Experiências com trabalho em equipe
   - Capacidade de liderança e influência

4. **Adaptabilidade e Crescimento:**
   - Como lida com mudanças e desafios
   - Interesse em aprendizado e desenvolvimento
   - Visão de carreira e objetivos futuros

5. **Red Flags ou Pontos de Atenção:**
   - Possíveis incompatibilidades culturais
   - Aspectos que podem gerar conflitos
   - Necessidades específicas do candidato

6. **Recomendação de Fit:**
   - Tipos de cultura organizacional mais adequados
   - Ambientes de trabalho ideais
   - Considerações para integração

Use apenas informações da transcrição: {transcript}
        """.strip(),
        variables=["transcript"],
        emoji="🤝",
        short_code="cultura",
        tags=["cultura", "fit", "valores", "motivação", "equipe"],
        display_order=4,
        settings={
            "max_tokens": 3500,
            "temperature": 0.6
        }
    )
    
    # 5. Custom/Flexible Prompt
    custom_prompt = PromptTemplate(
        name="Análise Personalizada",
        description="Prompt flexível para análises específicas conforme necessidade",
        category=PromptCategory.CUSTOM,
        status=PromptStatus.ACTIVE,
        prompt_text="""
Analise a transcrição da entrevista fornecida e responda em PORTUGUÊS.

{custom_instructions}

Base sua análise exclusivamente no conteúdo da transcrição: {transcript}

Seja específico, objetivo e forneça exemplos da conversa quando possível.
        """.strip(),
        variables=["transcript", "custom_instructions"],
        emoji="🎨",
        short_code="custom",
        tags=["personalizado", "flexível", "específico"],
        display_order=5,
        settings={
            "max_tokens": 4000,
            "temperature": 0.7
        }
    )
    
    # Create all prompts
    prompts = [
        interview_prompt,
        quick_summary_prompt,
        technical_prompt,
        cultural_prompt,
        custom_prompt
    ]
    
    created_count = 0
    for prompt in prompts:
        try:
            # Check if prompt already exists
            existing = await prompt_repo.get_by_short_code(prompt.short_code)
            if existing:
                print(f"⚠️  Prompt '{prompt.name}' já existe (short_code: {prompt.short_code})")
                continue
            
            await prompt_repo.create(prompt)
            print(f"✅ Criado: {prompt.name} ({prompt.short_code})")
            created_count += 1
            
        except Exception as e:
            print(f"❌ Erro ao criar prompt '{prompt.name}': {e}")
    
    print(f"\n🎉 Setup concluído! {created_count} prompts criados.")
    
    # Close database connection
    await MongoDB.disconnect()


async def list_existing_prompts():
    """List all existing prompts in the database"""
    await MongoDB.connect()
    
    prompt_repo = PromptRepository()
    prompts = await prompt_repo.get_all_active()
    
    if not prompts:
        print("📝 Nenhum prompt encontrado no banco de dados.")
        return
    
    print("📝 Prompts existentes:")
    print("-" * 60)
    
    for prompt in prompts:
        print(f"{prompt.emoji} {prompt.name}")
        print(f"   Código: {prompt.short_code}")
        print(f"   Categoria: {prompt.category}")
        print(f"   Status: {prompt.status}")
        print(f"   Usado: {prompt.usage_count} vezes")
        print(f"   ID: {prompt.id}")
        print()
    
    await MongoDB.disconnect()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Setup prompt templates")
    parser.add_argument("--list", action="store_true", help="List existing prompts")
    parser.add_argument("--create", action="store_true", help="Create initial prompts")
    
    args = parser.parse_args()
    
    if args.list:
        asyncio.run(list_existing_prompts())
    elif args.create:
        asyncio.run(create_initial_prompts())
    else:
        print("Usage: python setup_prompts.py --create | --list")
        parser.print_help()