#!/bin/sh

# O nome do arquivo que conterá todo o seu código para análise.
OUTPUT_FILE="analise_de_codigo_completo.txt"

# Apaga o arquivo de saída se ele já existir para garantir que está limpo.
> "$OUTPUT_FILE"

# --- PERSONALIZAÇÃO PARA PYTHON ---
# Adicione outros diretórios para ignorar, separados por |
# Ex: "pasta_de_dados|outra_pasta"
IGNORE_DIRS=".git|__pycache__|venv|.venv|env|.env|build|dist|.pytest_cache|.vscode|.idea|.ipynb_checkpoints"

# Adicione outras extensões de arquivo para ignorar, separadas por |
# Ex: "db|sqlite3"
IGNORE_EXTENSIONS="pyc|log|tmp|o|class|jar|war|ear|zip|tar.gz|db|sqlite3"
# --- FIM DA PERSONALIZAÇÃO ---

# ==============================================================================
# 1. ADICIONA A ÁRVORE DE DIRETÓRIOS NO INÍCIO DO ARQUIVO
# ==============================================================================
echo "--- ESTRUTURA DE DIRETÓRIOS (até 3 níveis) ---" >> "$OUTPUT_FILE"
# O comando tree -L 3 lista até 3 níveis de profundidade.
# A flag -I ignora os diretórios e arquivos especificados, tornando a árvore mais limpa.
tree -L 3 -I "$(echo $IGNORE_DIRS | sed 's/|/\\|/g')|$(basename "$0")|$OUTPUT_FILE" >> "$OUTPUT_FILE"
echo -e "\n\n--- CONTEÚDO DOS ARQUIVOS ---\n" >> "$OUTPUT_FILE"


# ==============================================================================
# 2. ADICIONA O CONTEÚDO DE CADA ARQUIVO
# ==============================================================================
echo "Gerando a lista de arquivos e seus conteúdos em $OUTPUT_FILE..."

find . -type f | grep -vE "/($IGNORE_DIRS)/" | grep -vE "\.($IGNORE_EXTENSIONS)$" | while read -r file
do
  # Ignora o próprio script de listagem e o arquivo de saída.
  if [ "$file" = "./$(basename "$0")" ] || [ "$file" = "./$OUTPUT_FILE" ]; then
    continue
  fi

  # Escreve o cabeçalho do arquivo e seu conteúdo no arquivo de saída.
  echo "--- Início do arquivo: $file ---" >> "$OUTPUT_FILE"
  cat "$file" >> "$OUTPUT_FILE"
  echo -e "\n--- Fim do arquivo: $file ---\n" >> "$OUTPUT_FILE"
done

echo "Concluído! A análise completa do seu projeto foi salva em $OUTPUT_FILE"