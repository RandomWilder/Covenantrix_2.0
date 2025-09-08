# core-rag-service/src/settings_manager.py
"""
Secure settings management for Covenantrix
Handles API keys and user preferences with system keyring storage
"""

import os
import json
import asyncio
import aiohttp
from pathlib import Path
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import logging

try:
    import keyring
    import keyring.backends.Windows
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    logging.warning("Keyring not available, falling back to environment variables only")


@dataclass
class ProviderConfig:
    """Configuration for an API provider"""
    name: str
    display_name: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    models: List[str] = None
    is_active: bool = False
    last_validated: Optional[datetime] = None
    validation_status: str = "unknown"  # unknown, valid, invalid, error


@dataclass
class UserSettings:
    """Complete user settings structure"""
    providers: Dict[str, ProviderConfig]
    preferences: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        
        # Convert provider configs
        for provider_name, config in data['providers'].items():
            if config['last_validated']:
                config['last_validated'] = config['last_validated'].isoformat()
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'UserSettings':
        """Create from dictionary"""
        # Parse datetime strings
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        
        # Parse provider configs
        providers = {}
        for provider_name, config_data in data['providers'].items():
            if config_data.get('last_validated'):
                config_data['last_validated'] = datetime.fromisoformat(config_data['last_validated'])
            
            providers[provider_name] = ProviderConfig(**config_data)
        
        data['providers'] = providers
        return cls(**data)


class SettingsManager:
    """
    Secure settings manager using system keyring for API keys
    """
    
    KEYRING_SERVICE = "CovenantrixRAG"
    SETTINGS_FILENAME = "user_settings.json"
    
    # Provider configurations
    SUPPORTED_PROVIDERS = {
        "openai": {
            "display_name": "OpenAI",
            "base_url": "https://api.openai.com/v1",
            "models": ["gpt-4o", "gpt-4o-mini", "text-embedding-3-small", "text-embedding-3-large"],
            "validation_endpoint": "/models"
        },
        "anthropic": {
            "display_name": "Anthropic",
            "base_url": "https://api.anthropic.com/v1", 
            "models": ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"],
            "validation_endpoint": "/messages"
        },
        "azure_openai": {
            "display_name": "Azure OpenAI",
            "base_url": None,  # User configurable
            "models": ["gpt-4o", "gpt-4o-mini", "text-embedding-ada-002"],
            "validation_endpoint": "/deployments"
        }
    }
    
    def __init__(self, working_dir: str = "./covenantrix_data"):
        self.working_dir = Path(working_dir)
        self.settings_dir = self.working_dir / "user_settings"
        self.settings_dir.mkdir(parents=True, exist_ok=True)
        
        self.settings_file = self.settings_dir / self.SETTINGS_FILENAME
        self._settings: Optional[UserSettings] = None
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
    
    def _get_keyring_key(self, provider: str) -> str:
        """Generate keyring key for provider"""
        return f"{provider}_api_key"
    
    def _store_api_key_secure(self, provider: str, api_key: str) -> bool:
        """Store API key securely using system keyring"""
        if not KEYRING_AVAILABLE:
            self.logger.warning(f"Keyring not available, cannot store {provider} API key securely")
            return False
        
        try:
            keyring_key = self._get_keyring_key(provider)
            keyring.set_password(self.KEYRING_SERVICE, keyring_key, api_key)
            self.logger.info(f"API key for {provider} stored securely in keyring")
            return True
        except Exception as e:
            self.logger.error(f"Failed to store {provider} API key in keyring: {e}")
            return False
    
    def _get_api_key_secure(self, provider: str) -> Optional[str]:
        """Retrieve API key securely from system keyring"""
        if not KEYRING_AVAILABLE:
            return None
        
        try:
            keyring_key = self._get_keyring_key(provider)
            api_key = keyring.get_password(self.KEYRING_SERVICE, keyring_key)
            return api_key
        except Exception as e:
            self.logger.error(f"Failed to retrieve {provider} API key from keyring: {e}")
            return None
    
    def _delete_api_key_secure(self, provider: str) -> bool:
        """Delete API key from system keyring"""
        if not KEYRING_AVAILABLE:
            return False
        
        try:
            keyring_key = self._get_keyring_key(provider)
            keyring.delete_password(self.KEYRING_SERVICE, keyring_key)
            self.logger.info(f"API key for {provider} deleted from keyring")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete {provider} API key from keyring: {e}")
            return False
    
    def _get_fallback_api_key(self, provider: str) -> Optional[str]:
        """Get API key from environment variables (fallback)"""
        env_var_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY", 
            "azure_openai": "AZURE_OPENAI_API_KEY"
        }
        
        env_var = env_var_map.get(provider)
        if env_var:
            return os.getenv(env_var)
        return None
    
    async def initialize(self) -> bool:
        """Initialize settings manager and load user settings"""
        try:
            await self.load_settings()
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize settings manager: {e}")
            return False
    
    async def load_settings(self) -> UserSettings:
        """Load user settings from file"""
        if self._settings is not None:
            return self._settings
        
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                self._settings = UserSettings.from_dict(data)
                
                # Load API keys from keyring
                for provider_name, config in self._settings.providers.items():
                    # First try keyring, then fallback to environment
                    api_key = self._get_api_key_secure(provider_name)
                    if not api_key:
                        api_key = self._get_fallback_api_key(provider_name)
                    
                    config.api_key = api_key
                
                self.logger.info("User settings loaded successfully")
                
            except Exception as e:
                self.logger.error(f"Failed to load settings: {e}")
                self._settings = self._create_default_settings()
        else:
            self._settings = self._create_default_settings()
        
        return self._settings
    
    def _create_default_settings(self) -> UserSettings:
        """Create default settings structure"""
        providers = {}
        
        for provider_id, provider_info in self.SUPPORTED_PROVIDERS.items():
            # Check for existing API keys in environment
            existing_key = self._get_fallback_api_key(provider_id)
            
            providers[provider_id] = ProviderConfig(
                name=provider_id,
                display_name=provider_info["display_name"],
                api_key=existing_key,
                base_url=provider_info["base_url"],
                models=provider_info["models"],
                is_active=existing_key is not None,
                validation_status="unknown" if existing_key else "missing"
            )
        
        now = datetime.now()
        return UserSettings(
            providers=providers,
            preferences={
                "default_provider": "openai",
                "auto_validate_keys": True,
                "cache_validation": True
            },
            created_at=now,
            updated_at=now
        )
    
    async def save_settings(self, exclude_api_keys: bool = True) -> bool:
        """Save settings to file (excluding API keys for security)"""
        if self._settings is None:
            return False
        
        try:
            # Create a copy for saving
            settings_copy = UserSettings(
                providers={},
                preferences=self._settings.preferences.copy(),
                created_at=self._settings.created_at,
                updated_at=datetime.now()
            )
            
            # Copy provider configs without API keys
            for provider_name, config in self._settings.providers.items():
                config_copy = ProviderConfig(
                    name=config.name,
                    display_name=config.display_name,
                    api_key=None if exclude_api_keys else config.api_key,
                    base_url=config.base_url,
                    models=config.models,
                    is_active=config.is_active,
                    last_validated=config.last_validated,
                    validation_status=config.validation_status
                )
                settings_copy.providers[provider_name] = config_copy
            
            # Save to file
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings_copy.to_dict(), f, indent=2, ensure_ascii=False)
            
            self.logger.info("Settings saved successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save settings: {e}")
            return False
    
    async def set_api_key(self, provider: str, api_key: str) -> bool:
        """Set API key for a provider"""
        if provider not in self.SUPPORTED_PROVIDERS:
            self.logger.error(f"Unsupported provider: {provider}")
            return False
        
        settings = await self.load_settings()
        
        # Store in keyring
        if not self._store_api_key_secure(provider, api_key):
            self.logger.warning(f"Failed to store {provider} API key in keyring, using memory only")
        
        # Update settings
        if provider not in settings.providers:
            provider_info = self.SUPPORTED_PROVIDERS[provider]
            settings.providers[provider] = ProviderConfig(
                name=provider,
                display_name=provider_info["display_name"],
                base_url=provider_info["base_url"],
                models=provider_info["models"]
            )
        
        settings.providers[provider].api_key = api_key
        settings.providers[provider].is_active = True
        settings.providers[provider].validation_status = "unknown"
        settings.providers[provider].last_validated = None
        
        return await self.save_settings()
    
    async def get_api_key(self, provider: str) -> Optional[str]:
        """Get API key for a provider"""
        settings = await self.load_settings()
        
        if provider in settings.providers:
            config = settings.providers[provider]
            if config.api_key:
                return config.api_key
        
        # Fallback to environment
        return self._get_fallback_api_key(provider)
    
    async def delete_api_key(self, provider: str) -> bool:
        """Delete API key for a provider"""
        settings = await self.load_settings()
        
        # Remove from keyring
        self._delete_api_key_secure(provider)
        
        # Update settings
        if provider in settings.providers:
            settings.providers[provider].api_key = None
            settings.providers[provider].is_active = False
            settings.providers[provider].validation_status = "missing"
            settings.providers[provider].last_validated = None
        
        return await self.save_settings()
    
    async def validate_api_key(self, provider: str, api_key: Optional[str] = None) -> Dict[str, Any]:
        """Validate API key for a provider"""
        if provider not in self.SUPPORTED_PROVIDERS:
            return {
                "valid": False,
                "error": f"Unsupported provider: {provider}",
                "provider": provider
            }
        
        # Use provided key or get from settings
        if api_key is None:
            api_key = await self.get_api_key(provider)
        
        if not api_key:
            return {
                "valid": False,
                "error": "No API key available",
                "provider": provider
            }
        
        # Validate based on provider
        try:
            if provider == "openai":
                return await self._validate_openai_key(api_key)
            elif provider == "anthropic":
                return await self._validate_anthropic_key(api_key)
            elif provider == "azure_openai":
                return await self._validate_azure_openai_key(api_key)
            else:
                return {
                    "valid": False,
                    "error": f"Validation not implemented for {provider}",
                    "provider": provider
                }
        except Exception as e:
            self.logger.error(f"API key validation failed for {provider}: {e}")
            return {
                "valid": False,
                "error": str(e),
                "provider": provider
            }
    
    async def _validate_openai_key(self, api_key: str) -> Dict[str, Any]:
        """Validate OpenAI API key"""
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            try:
                async with session.get(
                    "https://api.openai.com/v1/models",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        models = [model["id"] for model in data.get("data", [])]
                        
                        return {
                            "valid": True,
                            "provider": "openai",
                            "models": models,
                            "organization": response.headers.get("openai-organization"),
                            "validated_at": datetime.now().isoformat()
                        }
                    else:
                        error_data = await response.json() if response.content_type == 'application/json' else {}
                        return {
                            "valid": False,
                            "error": error_data.get("error", {}).get("message", f"HTTP {response.status}"),
                            "provider": "openai",
                            "status_code": response.status
                        }
                        
            except asyncio.TimeoutError:
                return {
                    "valid": False,
                    "error": "Request timeout - check your internet connection",
                    "provider": "openai"
                }
            except Exception as e:
                return {
                    "valid": False,
                    "error": str(e),
                    "provider": "openai"
                }
    
    async def _validate_anthropic_key(self, api_key: str) -> Dict[str, Any]:
        """Validate Anthropic API key - placeholder for future implementation"""
        return {
            "valid": False,
            "error": "Anthropic validation not yet implemented",
            "provider": "anthropic"
        }
    
    async def _validate_azure_openai_key(self, api_key: str) -> Dict[str, Any]:
        """Validate Azure OpenAI API key - placeholder for future implementation"""
        return {
            "valid": False,
            "error": "Azure OpenAI validation not yet implemented",
            "provider": "azure_openai"
        }
    
    async def get_all_settings(self) -> Dict[str, Any]:
        """Get all settings (excluding API keys for security)"""
        settings = await self.load_settings()
        
        # Return sanitized settings
        result = {
            "providers": {},
            "preferences": settings.preferences,
            "created_at": settings.created_at.isoformat(),
            "updated_at": settings.updated_at.isoformat()
        }
        
        for provider_name, config in settings.providers.items():
            result["providers"][provider_name] = {
                "name": config.name,
                "display_name": config.display_name,
                "base_url": config.base_url,
                "models": config.models,
                "is_active": config.is_active,
                "has_api_key": config.api_key is not None,
                "last_validated": config.last_validated.isoformat() if config.last_validated else None,
                "validation_status": config.validation_status
            }
        
        return result
    
    async def get_active_provider(self) -> Optional[str]:
        """Get the currently active provider"""
        settings = await self.load_settings()
        
        # Check for explicitly active provider
        for provider_name, config in settings.providers.items():
            if config.is_active and config.api_key:
                return provider_name
        
        # Fallback to default preference
        default_provider = settings.preferences.get("default_provider", "openai")
        if default_provider in settings.providers and settings.providers[default_provider].api_key:
            return default_provider
        
        return None
    
    async def update_validation_status(self, provider: str, validation_result: Dict[str, Any]) -> bool:
        """Update validation status for a provider"""
        settings = await self.load_settings()
        
        if provider in settings.providers:
            config = settings.providers[provider]
            config.last_validated = datetime.now()
            config.validation_status = "valid" if validation_result.get("valid") else "invalid"
            
            return await self.save_settings()
        
        return False
