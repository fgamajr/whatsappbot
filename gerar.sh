#!/bin/bash

# --- Configuração ---
# Diretório raiz do projeto (padrão: diretório atual)
PROJECT_ROOT="."

# Nome do arquivo de saída
OUTPUT_FILE="project_context.txt"

# Diretórios a serem completamente ignorados na árvore e na busca de arquivos.
# Adicione outros se necessário, como 'node_modules'.
EXCLUDE_DIRS=(
    '__pycache__'
    'venv'
    '.venv'
    'env'
    '.env'
    '.git'
    '.vscode'
    '.idea'
    'dist'
    'build'
    '*.egg-info'
    '.pytest_cache'
    'htmlcov'
    '.ipynb_checkpoints'
)

# Padrões de nome de arquivo a serem incluídos na seção de conteúdo.
# Sinta-se à vontade para adicionar ou remover tipos de arquivo (ex: '*.html', '*.css').
INCLUDE_PATTERNS=(
    -name '*.py'
    -o -name '*.pyi'
    -o -name 'requirements*.txt'
    -o -name 'README.md'
    -o -name 'pyproject.toml'
    -o -name 'Pipfile'
    -o -name 'Pipfile.lock'
    -o -name '*.ini'
    -o -name '*.toml'
    -o -name '*.yaml'
    -o -name '*.yml'
    -o -name '*.json'
    -o -name 'Dockerfile'
    -o -name 'docker-compose.yml'
    -o -name '*.sh'
)
# --- Fim da Configuração ---


echo "Gerando contexto do projeto em '$OUTPUT_FILE'..."

# Remove o arquivo de saída antigo, se existir
rm -f "$OUTPUT_FILE"

# --- Seção 1: Estrutura de Diretórios ---
echo "==================================================" > "$OUTPUT_FILE"
echo "           ESTRUTURA DO PROJETO (tree -L 3)       " >> "$OUTPUT_FILE"
echo "==================================================" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

# Constrói o padrão de exclusão para o comando 'tree'
TREE_IGNORE_PATTERN=$(IFS="|"; echo "${EXCLUDE_DIRS[*]}")
tree -L 3 -a -I "$TREE_IGNORE_PATTERN" "$PROJECT_ROOT" >> "$OUTPUT_FILE"

# --- Seção 2: Conteúdo dos Arquivos ---
echo "" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
echo "==================================================" >> "$OUTPUT_FILE"
echo "       CÓDIGO FONTE E ARQUIVOS DE CONFIGURAÇÃO    " >> "$OUTPUT_FILE"
echo "==================================================" >> "$OUTPUT_FILE"

# Constrói a condição de exclusão para o comando 'find'
PRUNE_CONDITIONS=()
for dir in "${EXCLUDE_DIRS[@]}"; do
    PRUNE_CONDITIONS+=(-o -path "*/$dir")
done
# Remove o '-o' inicial desnecessário
unset PRUNE_CONDITIONS[0]

# Encontra e concatena os arquivos relevantes, ignorando os diretórios excluídos
find "$PROJECT_ROOT" \( "${PRUNE_CONDITIONS[@]}" \) -prune -o -type f \( "${INCLUDE_PATTERNS[@]}" \) -print | sort | while IFS= read -r file; do
    # Verifica se o arquivo não está vazio
    if [ -s "$file" ]; then
        echo "" >> "$OUTPUT_FILE"
        echo "# --------------------------------------------------" >> "$OUTPUT_FILE"
        echo "# Arquivo: $file" >> "$OUTPUT_FILE"
        echo "# --------------------------------------------------" >> "$OUTPUT_FILE"
        cat "$file" >> "$OUTPUT_FILE"
    fi
done

echo ""
echo "✅ Processo concluído!"
echo "O contexto do projeto foi salvo em: $OUTPUT_FILE"
echo ""
echo "⚠️ IMPORTANTE: Revise o arquivo '$OUTPUT_FILE' antes de compartilhá-lo para garantir que nenhuma informação sensível (como senhas ou chaves de API) foi incluída."