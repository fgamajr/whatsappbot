from typing import List, Optional, Dict, Any, Tuple
import logging
from app.domain.entities.prompt import PromptTemplate, UserPromptPreference, PromptCategory, PromptStatus
from app.infrastructure.database.repositories.prompt import PromptRepository
from app.core.exceptions import AnalysisError

logger = logging.getLogger(__name__)


class PromptManagerService:
    """Service for managing AI prompt templates"""
    
    def __init__(self):
        self.prompt_repo = PromptRepository()
    
    async def get_user_prompt_options(self, user_id: str, category: Optional[PromptCategory] = None) -> List[Dict[str, Any]]:
        """Get formatted prompt options for user selection"""
        try:
            # Get user preferences
            user_pref = await self.prompt_repo.get_user_preference(user_id)
            
            # Get available prompts
            if category:
                prompts = await self.prompt_repo.get_by_category(category)
            else:
                prompts = await self.prompt_repo.get_all_active()
            
            # Format for user display
            options = []
            for i, prompt in enumerate(prompts, 1):
                is_default = user_pref and user_pref.default_prompt_id == prompt.id
                is_last_used = user_pref and user_pref.last_selected_prompt_id == prompt.id
                
                option = {
                    "number": i,
                    "id": prompt.id,
                    "name": prompt.name,
                    "description": prompt.description,
                    "emoji": prompt.emoji or "📝",
                    "short_code": prompt.short_code,
                    "category": prompt.category,
                    "is_default": is_default,
                    "is_last_used": is_last_used,
                    "usage_count": prompt.usage_count
                }
                
                options.append(option)
            
            return options
            
        except Exception as e:
            logger.error("Failed to get user prompt options", extra={
                "error": str(e),
                "user_id": user_id
            })
            raise
    
    async def select_prompt_for_user(self, user_id: str, prompt_identifier: str) -> Optional[PromptTemplate]:
        """Select prompt by ID, short code, or number"""
        try:
            prompt = None
            
            # Try by ID first
            if len(prompt_identifier) > 10:  # Likely an ID
                prompt = await self.prompt_repo.get_by_id(prompt_identifier)
            
            # Try by short code
            if not prompt:
                prompt = await self.prompt_repo.get_by_short_code(prompt_identifier)
            
            # Try by number (from user options) - use interview_analysis category
            if not prompt and prompt_identifier.isdigit():
                from app.domain.entities.prompt import PromptCategory
                options = await self.get_user_prompt_options(user_id, PromptCategory.INTERVIEW_ANALYSIS)
                prompt_num = int(prompt_identifier)
                if 1 <= prompt_num <= len(options):
                    prompt_id = options[prompt_num - 1]["id"]
                    prompt = await self.prompt_repo.get_by_id(prompt_id)
                    
                    logger.info("Prompt selected by number", extra={
                        "user_id": user_id,
                        "prompt_number": prompt_num,
                        "selected_prompt_id": prompt_id,
                        "selected_prompt_name": prompt.name if prompt else "not_found",
                        "total_options": len(options)
                    })
            
            if prompt:
                # Update user preference
                await self._update_user_last_selected(user_id, prompt.id)
                
                # Mark prompt as used (with error handling)
                try:
                    prompt.mark_used()
                    await self.prompt_repo.update(prompt)
                except Exception as update_error:
                    # Log but don't fail the selection
                    logger.warning("Failed to update prompt usage stats", extra={
                        "error": str(update_error),
                        "prompt_id": prompt.id
                    })
                
                logger.info("Prompt selected for user", extra={
                    "user_id": user_id,
                    "prompt_id": prompt.id,
                    "prompt_name": prompt.name
                })
            
            return prompt
            
        except Exception as e:
            logger.error("Failed to select prompt for user", extra={
                "error": str(e),
                "user_id": user_id,
                "prompt_identifier": prompt_identifier
            })
            raise
    
    async def get_default_prompt_for_category(self, category: PromptCategory) -> Optional[PromptTemplate]:
        """Get the most popular prompt for a category as default"""
        try:
            prompts = await self.prompt_repo.get_by_category(category)
            if prompts:
                # Return most used prompt as default
                return max(prompts, key=lambda p: p.usage_count)
            return None
            
        except Exception as e:
            logger.error("Failed to get default prompt", extra={
                "error": str(e),
                "category": category
            })
            raise
    
    async def format_prompt_for_analysis(self, prompt: PromptTemplate, **kwargs) -> str:
        """Format prompt with variables"""
        try:
            return prompt.format_prompt(**kwargs)
            
        except Exception as e:
            logger.error("Failed to format prompt", extra={
                "error": str(e),
                "prompt_id": prompt.id
            })
            raise AnalysisError(f"Failed to format prompt: {str(e)}")
    
    async def create_prompt_menu(self, user_id: str, category: Optional[PromptCategory] = None) -> str:
        """Create formatted menu text for user"""
        try:
            options = await self.get_user_prompt_options(user_id, category)
            
            if not options:
                return "❌ Nenhum prompt disponível no momento."
            
            menu_text = "📝 **Escolha o tipo de análise:**\n\n"
            
            for option in options:
                line = f"{option['number']}️⃣ {option['emoji']} **{option['name']}**\n"
                line += f"   {option['description']}\n"
                
                # Add usage info
                if option['usage_count'] > 0:
                    line += f"   📊 Usado {option['usage_count']} vezes\n"
                
                # Mark default or last used
                if option['is_default']:
                    line += f"   ⭐ Padrão\n"
                elif option['is_last_used']:
                    line += f"   🕐 Último usado\n"
                
                menu_text += line + "\n"
            
            menu_text += "\n💡 **Como escolher:**\n"
            menu_text += "• Digite o número (ex: `1`)\n"
            
            # Add short codes if available
            short_codes = [opt['short_code'] for opt in options if opt['short_code']]
            if short_codes:
                menu_text += f"• Digite o código (ex: `{short_codes[0]}`)\n"
            
            menu_text += "• Ou digite `padrão` para usar o mais popular"
            
            return menu_text
            
        except Exception as e:
            logger.error("Failed to create prompt menu", extra={
                "error": str(e),
                "user_id": user_id
            })
            return "❌ Erro ao carregar opções de análise."
    
    async def _update_user_last_selected(self, user_id: str, prompt_id: str):
        """Update user's last selected prompt"""
        try:
            user_pref = await self.prompt_repo.get_user_preference(user_id)
            
            if not user_pref:
                user_pref = UserPromptPreference(user_id=user_id)
            
            user_pref.last_selected_prompt_id = prompt_id
            await self.prompt_repo.save_user_preference(user_pref)
            
        except Exception as e:
            logger.error("Failed to update user last selected", extra={
                "error": str(e),
                "user_id": user_id,
                "prompt_id": prompt_id
            })
    
    async def set_user_default_prompt(self, user_id: str, prompt_id: str) -> bool:
        """Set user's default prompt"""
        try:
            # Verify prompt exists and is active
            prompt = await self.prompt_repo.get_by_id(prompt_id)
            if not prompt or not prompt.is_active():
                return False
            
            user_pref = await self.prompt_repo.get_user_preference(user_id)
            if not user_pref:
                user_pref = UserPromptPreference(user_id=user_id)
            
            user_pref.default_prompt_id = prompt_id
            await self.prompt_repo.save_user_preference(user_pref)
            
            logger.info("User default prompt set", extra={
                "user_id": user_id,
                "prompt_id": prompt_id,
                "prompt_name": prompt.name
            })
            
            return True
            
        except Exception as e:
            logger.error("Failed to set user default prompt", extra={
                "error": str(e),
                "user_id": user_id,
                "prompt_id": prompt_id
            })
            return False
    
    async def get_user_default_or_popular(self, user_id: str, category: PromptCategory) -> Optional[PromptTemplate]:
        """Get user's default prompt or most popular for category"""
        try:
            # Try user's default first
            user_pref = await self.prompt_repo.get_user_preference(user_id)
            if user_pref and user_pref.default_prompt_id:
                prompt = await self.prompt_repo.get_by_id(user_pref.default_prompt_id)
                if prompt and prompt.is_active() and prompt.category == category:
                    return prompt
            
            # Fallback to most popular
            return await self.get_default_prompt_for_category(category)
            
        except Exception as e:
            logger.error("Failed to get user default or popular prompt", extra={
                "error": str(e),
                "user_id": user_id,
                "category": category
            })
            raise