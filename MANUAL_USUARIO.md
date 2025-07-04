# 📖 Guia de Usuário: Seu Assistente de Entrevistas no Telegram

Bem-vindo! Este guia vai te ensinar a configurar e usar seu assistente pessoal de IA para analisar entrevistas em áudio diretamente pelo Telegram.

## O que este programa faz?

De forma simples:
1.  Você envia um **áudio de uma entrevista** para o seu bot pessoal no Telegram.
2.  O robô "ouve" o áudio e **transcreve** toda a conversa.
3.  Uma Inteligência Artificial (IA) **analisa** o conteúdo da transcrição.
4.  Você recebe uma **análise completa** de volta no seu Telegram.

## Como Funciona? (O Desenho)

O processo todo pode ser desenhado assim:

```
   +------------------+      +----------------------+      +--------------------+
   |                  |      |                      |      |                    |
   |  Você envia o    |----->|   Nosso Robô entra   |----->|   A Análise é      |
   |  Áudio (Telegram)|      |   em ação:           |      |   enviada para     |
   |                  |      |                      |      |   Você (Telegram)  |
   +------------------+      |   1. Transcreve      |      |                    |
                             |   2. Analisa com IA  |      +--------------------+
                             |                      |
                             +----------------------+
```

## 1. Configuração Inicial (Criando seu Robô)

Antes de tudo, você precisa ter seu próprio robô no Telegram. É ele quem vai receber seus áudios. É fácil e rápido!

#### **Passo A: Crie o Bot com o "Pai dos Bots"**

1.  No Telegram, procure por `@BotFather` (ele tem um selo de verificação azul).
2.  Inicie uma conversa com ele e digite o comando: `/newbot`
3.  O BotFather vai pedir um nome para o seu robô (ex: "Analisador de Entrevistas").
4.  Depois, ele pedirá um nome de usuário, que deve terminar com "bot" (ex: `AnalisadorDeEntrevistasBot`).
5.  Pronto! O BotFather vai te dar uma mensagem de sucesso com um **token de acesso (API)**. Guarde este token, ele é a "chave secreta" do seu robô. Vai parecer com algo assim: `123456:ABC-DEF1234...`

#### **Passo B: Descubra sua Identificação (Chat ID)**

Agora, precisamos saber qual é a sua identificação no Telegram, para que o robô saiba que você é o administrador e possa te enviar as análises.

1.  No Telegram, procure por `@userinfobot`.
2.  Inicie uma conversa com ele. Ele imediatamente mostrará suas informações, incluindo seu **`Id`**. Guarde esse número.

#### **Passo C: Ajuste o Painel de Controle**

Agora que você tem o token e seu ID, vamos configurar o programa.

1.  Na pasta do projeto, encontre o arquivo `.env.example`.
2.  Faça uma **cópia** desse arquivo e renomeie a cópia para `.env`.
3.  Abra o novo arquivo `.env` e preencha as seguintes informações:

    *   `GEMINI_API_KEY`: Cole aqui sua chave de acesso para a IA do Google (Gemini).
    *   `TELEGRAM_BOT_TOKEN`: Cole aqui o **token de acesso** que o BotFather te deu.
    *   `ADMIN_CHAT_ID`: Cole aqui o seu **Id** que o `@userinfobot` te informou.
    *   `TELEGRAM_WEBHOOK_URL`: Esta é a URL pública pela qual o Telegram se comunicará com seu robô. Se você for rodar em um servidor, use a URL dele (ex: `https://seu-dominio.com`). Se for testar localmente, precisará de uma ferramenta como o `ngrok` para criar uma URL temporária.

## 2. Colocando para Rodar

Com a configuração pronta, ligar o sistema é muito fácil (requer Docker).

1.  Abra seu terminal (a tela preta de comandos) e, na pasta do projeto, digite:
    ```bash
    docker-compose up -d
    ```
    Isso inicia o robô em segundo plano.

2.  **Passo Final e Crucial:** Diga ao Telegram para onde enviar as mensagens. Copie o link abaixo, substitua `SEU_TOKEN` e `SUA_URL` pelos valores que você configurou no arquivo `.env`, e cole no seu navegador:

    `https://api.telegram.org/bot<SEU_TOKEN>/setWebhook?url=<SUA_URL>/api/v1/messaging/telegram/webhook`

    Se tudo der certo, você verá uma mensagem de sucesso no navegador.

Para desligar tudo, use o comando no terminal: `docker-compose down`

## 3. Usando o Assistente

Agora a parte divertida:

1.  No Telegram, procure pelo seu robô usando o **@nomedeusuario** que você criou.
2.  Inicie uma conversa e **envie um áudio** com a entrevista.
3.  Aguarde alguns instantes.
4.  Você receberá a análise completa na mesma conversa!

## 4. Vendo Seus Resultados

Para baixar um relatório com todas as entrevistas processadas, acesse no seu navegador:
`http://localhost:8000/api/export/interviews`

Isso fará o download de um arquivo compatível com Excel.
