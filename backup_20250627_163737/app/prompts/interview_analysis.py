INTERVIEW_ANALYSIS_PROMPT = """
Com base APENAS na transcrição da entrevista fornecida (que contém timestamps e diálogos), gere um relatório abrangente que responda às seguintes questões.
Estruture a saída com títulos claros para cada questão. Seja detalhado, mas conciso. Responda em PORTUGUÊS.

IMPORTANTE: A transcrição contém apenas timestamps [MM:SS-MM:SS] seguidos do texto falado. Analise o conteúdo para identificar as diferentes vozes e o contexto da entrevista.

1. **Experiência Profissional e Conquistas:**
   - Resuma a trajetória profissional mencionada na entrevista, incluindo cargos principais, empresas e progressão na carreira
   - Destaque as conquistas, projetos ou realizações mais significativas relatadas
   - Anote quaisquer certificações, educação ou habilidades técnicas relevantes discutidas
   - Inclua exemplos específicos fornecidos durante a conversa

2. **Histórico Pessoal:**
   - Descreva o histórico pessoal relevante, motivações ou experiências de vida compartilhadas
   - Inclua interesses pessoais, valores ou circunstâncias que possam ser relevantes para o perfil profissional
   - Anote quaisquer desafios superados ou perspectivas únicas mencionadas

3. **Avaliação de Personalidade e Habilidades:**
   - Com base na linguagem, tom e exemplos fornecidos, identifique os principais traços de personalidade
   - Avalie habilidades interpessoais como estilo de comunicação, abordagem de resolução de problemas, capacidades de trabalho em equipe
   - Anote qualidades de liderança, adaptabilidade e outros indicadores comportamentais observados
   - Inclua exemplos específicos da transcrição que apoiem essas avaliações
   - Observe a qualidade das respostas e a estrutura do pensamento demonstrada

4. **Pontos Fortes e Áreas de Desenvolvimento:**
   - Liste os principais pontos fortes identificados com base na entrevista
   - Identifique possíveis áreas de desenvolvimento ou lacunas mencionadas
   - Forneça recomendações específicas baseadas no perfil apresentado

5. **Adequação Cultural e Motivacional:**
   - Avalie a motivação para a posição/empresa discutida
   - Identifique valores e características que podem indicar boa adequação cultural
   - Analise expectativas de carreira e alinhamento com objetivos organizacionais

6. **Impressões Gerais:**
   - Forneça uma avaliação geral do candidato baseada na entrevista
   - Destaque aspectos únicos ou diferenciadores observados
   - Inclua recomendações finais sobre o perfil apresentado

Certifique-se de que todas as informações vêm diretamente da transcrição e evite fazer suposições além do que foi explicitamente discutido.
Analise o contexto e o fluxo da conversa para distinguir entre perguntas e respostas, mesmo sem identificação explícita de locutores.
"""