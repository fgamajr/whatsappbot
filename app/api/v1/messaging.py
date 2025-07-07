from fastapi import APIRouter, Request, Response, BackgroundTasks
from typing import Dict, Set
import logging
from app.services.message_handler import MessageHandler
from app.services.prompt_manager import PromptManagerService
from app.services.user_session_manager import UserSessionManager
from app.services.authorization import authorization_service
from app.domain.entities.prompt import PromptCategory
from app.infrastructure.messaging.factory import MessagingProviderFactory
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Simple in-memory cache for duplicate detection
processed_messages: Set[str] = set()


@router.get("/whatsapp")
async def verify_whatsapp_webhook(request: Request):
    """Verify webhook with WhatsApp"""
    provider = MessagingProviderFactory.create_provider("whatsapp")
    
    query_params = dict(request.query_params)
    
    if provider.validate_webhook({}, query_params):
        challenge = query_params.get("hub.challenge", "")
        logger.info("WhatsApp webhook verified successfully")
        return Response(content=challenge, status_code=200)
    else:
        logger.warning("WhatsApp webhook verification failed")
        return Response(status_code=403)


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    """WhatsApp webhook endpoint"""
    return await _handle_webhook(request, background_tasks, "whatsapp")


@router.post("/telegram")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    """Telegram webhook endpoint"""
    return await _handle_webhook(request, background_tasks, "telegram")


async def _handle_webhook(request: Request, background_tasks: BackgroundTasks, provider_name: str):
    """Generic webhook handler for any messaging provider"""
    try:
        data = await request.json()
        provider = MessagingProviderFactory.create_provider(provider_name)
        
        # Validate webhook
        if not provider.validate_webhook(data, {}):
            return Response(status_code=200)
        
        # Extract message data
        standard_message = provider.extract_message_data(data)
        if not standard_message:
            return Response(status_code=200)
        
        # Check user authorization
        is_authorized, user, reason = await authorization_service.check_user_authorization(
            provider_name, standard_message.from_number
        )
        
        if not is_authorized:
            logger.warning("Unauthorized access attempt", extra={
                "provider": provider_name,
                "from_number": standard_message.from_number,
                "reason": reason
            })
            
            # Send appropriate message based on the reason
            if reason == "User not authorized":
                unauthorized_message = (
                    "🚫 **Acesso Não Autorizado**\n\n"
                    "Este bot está restrito a usuários autorizados.\n"
                    "Para solicitar acesso, entre em contato:\n\n"
                    f"{settings.ADMIN_CONTACT_INFO}\n\n"
                    f"🆔 **Seu ID:** `{standard_message.from_number}`\n"
                    "ℹ️ Informe este ID e o motivo do acesso."
                )
            elif "limit exceeded" in reason.lower():
                unauthorized_message = (
                    "⚠️ **Limite de Uso Excedido**\n\n"
                    "Você atingiu o limite de mensagens permitidas.\n"
                    "Para aumentar seu limite, entre em contato:\n\n"
                    f"{settings.ADMIN_CONTACT_INFO}\n\n"
                    f"📊 Status: {reason}"
                )
            elif "suspended" in reason.lower():
                unauthorized_message = (
                    "⛔ **Conta Suspensa**\n\n"
                    "Sua conta foi suspensa temporariamente.\n"
                    "Para mais informações, entre em contato:\n\n"
                    f"{settings.ADMIN_CONTACT_INFO}"
                )
            elif "expired" in reason.lower():
                unauthorized_message = (
                    "⏰ **Acesso Expirado**\n\n"
                    "Seu acesso ao bot expirou.\n"
                    "Para renovar seu acesso, entre em contato:\n\n"
                    f"{settings.ADMIN_CONTACT_INFO}"
                )
            else:
                unauthorized_message = (
                    "❌ **Acesso Negado**\n\n"
                    "Não foi possível processar sua solicitação.\n"
                    "Entre em contato:\n\n"
                    f"{settings.ADMIN_CONTACT_INFO}\n\n"
                    f"ℹ️ Detalhes: {reason}"
                )
            
            # Send unauthorized message
            try:
                await provider.send_text_message(standard_message.from_number, unauthorized_message)
            except Exception as send_error:
                logger.error("Failed to send unauthorized message", extra={
                    "error": str(send_error),
                    "provider": provider_name,
                    "from_number": standard_message.from_number
                })
            
            return Response(status_code=200)
        
        # Record message usage for authorized user
        await authorization_service.record_message_usage(provider_name, standard_message.from_number)
        
        # Check for duplicates
        message_id = standard_message.message_id
        if message_id in processed_messages:
            logger.info("Duplicate message ignored", extra={
                "message_id": message_id,
                "provider": provider_name
            })
            return Response(status_code=200)
        
        # Add to cache
        processed_messages.add(message_id)
        
        # Clean cache if too large
        if len(processed_messages) > settings.MAX_CACHE_SIZE:
            processed_messages.clear()
        
        # Convert to legacy format for compatibility
        message_data = standard_message.to_dict()
        
        # Handle different message types
        if standard_message.message_type.value == "audio":
            # Send immediate acknowledgment
            await provider.send_text_message(
                standard_message.from_number,
                "🎵 Áudio recebido! Iniciando processamento...\n"
                "⚡ Resposta imediata garantida\n"
                "🔄 Processamento em background iniciado\n"
                "📱 Você receberá updates regulares!"
            )
            
            # Schedule background processing
            handler = MessageHandler(provider)
            background_tasks.add_task(handler.process_audio_message, message_data)
            
            logger.info("Audio processing scheduled", extra={
                "message_id": message_id,
                "from": standard_message.from_number,
                "provider": provider_name
            })
        
        elif standard_message.message_type.value == "text":
            # Handle text commands immediately
            await _handle_text_message(message_data, provider)
        
        return Response(status_code=200)
        
    except Exception as e:
        logger.error("Webhook processing error", extra={
            "error": str(e),
            "provider": provider_name
        })
        return Response(status_code=500)


async def _handle_text_message(message_data: Dict, provider):
    """Handle text commands immediately"""
    from_number = message_data["from"]
    text = message_data["content"].strip()  # Don't lowercase for custom instructions
    text_lower = text.lower()
    
    prompt_manager = PromptManagerService()
    session_manager = UserSessionManager()
    
    # Check if user is in a multi-step flow
    if await session_manager.is_waiting_for_custom_instructions(from_number):
        # User is providing custom instructions
        prompt_id = await session_manager.process_custom_instructions(from_number, text)
        if prompt_id:
            preview = text[:200] + ('...' if len(text) > 200 else '')
            await provider.send_text_message(
                from_number,
                "✅ Instruções personalizadas salvas!\n\n"
                "📝 Suas instruções:\n"
                f"\"{preview}\"\n\n"
                "🎵 Agora envie seu áudio para processamento!"
            )
        return
    
    # Regular command processing (with lowercase)
    text = text_lower
    
    if text in ["help", "ajuda", "/help"]:
        help_message = """
📋 *Bot de Relatório de Entrevistas* - Sistema Enterprise

🎵 **Processamento em Background:**
• Resposta imediata (<1s)
• Processamento paralelo de áudios longos
• Progress updates em tempo real
• Arquitetura limpa e escalável

📄 **Você receberá 2 documentos:**
1️⃣ **TRANSCRIÇÃO** - Texto completo com timestamps precisos
2️⃣ **ANÁLISE** - Relatório estruturado profissional

🚀 **Como usar:**
• Envie o áudio da entrevista (QUALQUER duração)
• Escolha o tipo de análise desejada

💡 **Comandos úteis:**
• `help` - Esta mensagem
• `prompts` - Ver tipos de análise disponíveis
• `status` - Informações do sistema
• `padrão` - Usar análise mais popular
• `id` - Ver seu ID para solicitar acesso
        """
        await provider.send_text_message(from_number, help_message)
    
    elif text in ["prompts", "analises", "tipos", "opcoes", "opções"]:
        menu = await prompt_manager.create_prompt_menu(from_number, PromptCategory.INTERVIEW_ANALYSIS)
        await provider.send_text_message(from_number, menu)
    
    elif text in ["padrao", "padrão", "default", "popular"]:
        default_prompt = await prompt_manager.get_default_prompt_for_category(PromptCategory.INTERVIEW_ANALYSIS)
        if default_prompt:
            await prompt_manager.set_user_default_prompt(from_number, default_prompt.id)
            await provider.send_text_message(
                from_number,
                f"✅ Padrão definido: {default_prompt.emoji} {default_prompt.name}\n\n"
                f"Agora envie seu áudio para processamento!"
            )
        else:
            await provider.send_text_message(
                from_number,
                "❌ Nenhum prompt padrão disponível no momento."
            )
    
    elif text == "status":
        status_message = f"""
📊 *System Status*

⚡ **Mode:** Background processing enabled
🚀 **Architecture:** Clean & Scalable
💾 **Cache:** {len(processed_messages)} messages processed
🛡️ **Protection:** Anti-duplicate enabled
🎙️ **Transcription:** Whisper + Timestamps
🧠 **Analysis:** Gemini AI (Prompts Dinâmicos)
🗄️ **Database:** MongoDB Atlas

📝 **Tipos de Análise:** Digite `prompts` para ver opções
        """
        await provider.send_text_message(from_number, status_message)
    
    elif text in ["id", "myid", "meu id", "chat id", "chatid"]:
        id_message = f"""
🆔 **Suas Informações de Identificação**

📱 **Seu ID:** `{from_number}`
🤖 **Plataforma:** {provider_name.title()}

ℹ️ Use este ID para solicitar acesso ao administrador.
        """
        await provider.send_text_message(from_number, id_message)
    
    elif text.isdigit() or text in ["entrevista", "resumo", "tecnico", "técnico", "cultura", "custom"]:
        # User is selecting a prompt
        logger.info("Processing prompt selection", extra={
            "user_input": text,
            "from_number": from_number,
            "is_digit": text.isdigit()
        })
        
        # Special handling for custom prompt
        if text == "custom":
            custom_prompt = await prompt_manager.prompt_repo.get_by_short_code("custom")
            if custom_prompt:
                # Set user to waiting for custom instructions
                await session_manager.set_waiting_for_custom_instructions(from_number, custom_prompt.id)
                
                await provider.send_text_message(
                    from_number,
                    f"🎨 {custom_prompt.emoji} **Análise Personalizada** selecionada!\n\n"
                    f"📝 **Digite suas instruções personalizadas:**\n\n"
                    f"Exemplo:\n"
                    f"\"Foque apenas nas habilidades de liderança e gestão de equipe. "
                    f"Avalie a capacidade de tomar decisões sob pressão.\"\n\n"
                    f"💡 **Dica:** Seja específico sobre o que você quer analisar na entrevista."
                )
                return
            else:
                await provider.send_text_message(
                    from_number,
                    "❌ Prompt personalizado não disponível no momento."
                )
                return
        
        # Regular prompt selection
        prompt = await prompt_manager.select_prompt_for_user(from_number, text)
        if prompt:
            logger.info("Prompt selected successfully", extra={
                "selected_prompt_id": prompt.id,
                "selected_prompt_name": prompt.name,
                "user_input": text
            })
            
            await provider.send_text_message(
                from_number,
                f"✅ Análise selecionada: {prompt.emoji} {prompt.name}\n\n"
                f"{prompt.description}\n\n"
                f"🎵 Agora envie seu áudio para processamento!"
            )
        else:
            logger.warning("Prompt selection failed", extra={
                "user_input": text,
                "from_number": from_number
            })
            
            await provider.send_text_message(
                from_number,
                f"❌ Opção '{text}' não encontrada.\n\n"
                f"Digite `prompts` para ver as opções disponíveis."
            )
    
    else:
        await provider.send_text_message(
            from_number, 
            "👋 Envie-me uma gravação de áudio de entrevista!\n\n"
            "📝 **Novo:** Escolha o tipo de análise\n"
            "• Digite `prompts` para ver opções\n"
            "• Ou envie o áudio direto (usará análise padrão)\n\n"
            "⚡ Resposta imediata + processamento enterprise!"
        )