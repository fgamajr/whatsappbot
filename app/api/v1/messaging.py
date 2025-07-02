from fastapi import APIRouter, Request, Response, BackgroundTasks
from typing import Dict, Set
import logging
from app.services.message_handler import MessageHandler
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
    text = message_data["content"].lower().strip()
    
    if text in ["help", "ajuda", "/help"]:
        help_message = """
📋 *Bot de Relatório de Entrevistas* - Sistema Enterprise

🎵 **Processamento em Background:**
• Resposta imediata (<1s)
• Processamento paralelo de áudios longos
• Chunks otimizados de 15min
• Progress updates em tempo real
• Arquitetura limpa e escalável

📄 **Você receberá 2 documentos:**
1️⃣ **TRANSCRIÇÃO** - Texto completo com timestamps precisos
2️⃣ **ANÁLISE** - Relatório estruturado profissional

🎙️ **Transcrição:**
• Timestamps precisos [MM:SS-MM:SS]
• Texto completo sem identificação de locutores
• Análise inteligente do contexto da conversa

🚀 **Como usar:**
Apenas envie o áudio da entrevista (QUALQUER duração)!

💡 **Comandos úteis:**
• `help` - Esta mensagem
• `status` - Informações do sistema
        """
        await provider.send_text_message(from_number, help_message)
    
    elif text == "status":
        status_message = f"""
📊 *System Status*

⚡ **Mode:** Background processing enabled
🚀 **Architecture:** Clean & Scalable
💾 **Cache:** {len(processed_messages)} messages processed
🛡️ **Protection:** Anti-duplicate enabled
🎙️ **Transcription:** Whisper + Timestamps
🧠 **Analysis:** Gemini AI
🗄️ **Database:** MongoDB Atlas

🎵 **Transcrição:** Apenas timestamps (sem locutores)
        """
        await provider.send_text_message(from_number, status_message)
    
    else:
        await provider.send_text_message(
            from_number, 
            "👋 Envie-me uma gravação de áudio de entrevista!\n⚡ Resposta imediata + processamento enterprise em background!\n🎙️ Transcrição com timestamps precisos"
        )