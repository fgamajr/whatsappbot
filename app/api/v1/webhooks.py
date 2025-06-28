from fastapi import APIRouter, Request, Response, BackgroundTasks
from typing import Dict, Set
import logging
from app.services.message_handler import MessageHandler
from app.domain.value_objects.phone_number import BrazilianPhoneNumber
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Simple in-memory cache for duplicate detection
processed_messages: Set[str] = set()


@router.get("")
async def verify_webhook(request: Request):
    """Verify webhook with WhatsApp"""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("Webhook verified successfully")
        return Response(content=challenge, status_code=200)
    else:
        logger.warning("Webhook verification failed")
        return Response(status_code=403)


@router.post("")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    """Main webhook endpoint - immediate response with background processing"""
    try:
        data = await request.json()
        
        # Quick validation
        if not _is_valid_message(data):
            return Response(status_code=200)
        
        # Extract message data
        message_data = _extract_message_data(data)
        if not message_data:
            return Response(status_code=200)
        
        # Handle different message types
        if message_data["type"] == "audio":
            # Schedule background processing
            handler = MessageHandler()
            background_tasks.add_task(handler.process_audio_message, message_data)
            
            logger.info("Audio processing scheduled", extra={
                "message_id": message_data["message_id"],
                "from": message_data["from"]
            })
        
        elif message_data["type"] == "text":
            # Handle text commands immediately
            await _handle_text_message(message_data)
        
        return Response(status_code=200)
        
    except Exception as e:
        logger.error("Webhook processing error", extra={
            "error": str(e)
        })
        return Response(status_code=500)


def _is_valid_message(data: dict) -> bool:
    """Check if webhook contains valid message"""
    try:
        entry = data.get("entry", [])
        if not entry:
            return False
            
        changes = entry[0].get("changes", [])
        if not changes:
            return False
            
        value = changes[0].get("value", {})
        
        # Ignore status updates
        if "statuses" in value:
            return False
        
        # Check for messages
        messages = value.get("messages", [])
        return bool(messages)
        
    except (IndexError, KeyError):
        return False


def _extract_message_data(data: dict) -> Dict:
    """Extract message data with duplicate protection"""
    try:
        messages = data["entry"][0]["changes"][0]["value"]["messages"][0]
        
        message_id = messages["id"]
        message_type = messages["type"]
        from_number = messages["from"]
        
        # Check for duplicates
        if message_id in processed_messages:
            logger.info("Duplicate message ignored", extra={
                "message_id": message_id
            })
            return None
        
        # Add to cache
        processed_messages.add(message_id)
        
        # Clean cache if too large
        if len(processed_messages) > settings.MAX_CACHE_SIZE:
            processed_messages.clear()
        
        # Validate and fix phone number
        try:
            phone = BrazilianPhoneNumber(number=from_number)
            from_number = phone.number
        except:
            pass  # Use original number if validation fails
        
        result = {
            "from": from_number,
            "type": message_type,
            "message_id": message_id,
            "timestamp": messages.get("timestamp")
        }
        
        if message_type == "audio":
            result["media_id"] = messages["audio"]["id"]
        elif message_type == "text":
            result["content"] = messages["text"]["body"]
        
        return result
        
    except (KeyError, IndexError) as e:
        logger.error("Error extracting message data", extra={
            "error": str(e)
        })
        return None


async def _handle_text_message(message_data: Dict):
    """Handle text commands immediately"""
    from app.infrastructure.whatsapp.client import WhatsAppClient
    
    whatsapp = WhatsAppClient()
    from_number = message_data["from"]
    text = message_data["content"].lower().strip()
    
    if text in ["help", "ajuda", "/help"]:
        help_message = """
📋 *Bot de Relatório de Entrevistas* - Sistema Enterprise

🎵 **Processamento em Background:**
• Resposta imediata ao WhatsApp (<1s)
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
        await whatsapp.send_text_message(from_number, help_message)
    
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
        await whatsapp.send_text_message(from_number, status_message)
    
    else:
        await whatsapp.send_text_message(
            from_number, 
            "👋 Envie-me uma gravação de áudio de entrevista!\n⚡ Resposta imediata + processamento enterprise em background!\n🎙️ Transcrição com timestamps precisos"
        )