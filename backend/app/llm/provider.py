"""LLM provider abstraction.

Supports OpenAI, Google Gemini, and local Ollama for AI reasoning.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from loguru import logger

from app.config import settings


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate(self, prompt: str, system: str = "") -> str:
        """Generate a completion from the LLM."""
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the provider is available."""
        ...


class OpenAIProvider(LLMProvider):
    """OpenAI API provider (GPT-4o)."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o") -> None:
        self.api_key = api_key or settings.openai_api_key
        self.model = model
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client

    async def generate(self, prompt: str, system: str = "") -> str:
        try:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=4096,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return f"[LLM Error: {e}]"

    async def is_available(self) -> bool:
        return bool(self.api_key)


class GeminiProvider(LLMProvider):
    """Google Gemini API provider."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-1.5-flash") -> None:
        self.api_key = api_key or settings.gemini_api_key
        self.model = model
        self._client = None

    async def generate(self, prompt: str, system: str = "") -> str:
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(
                self.model,
                system_instruction=system if system else None,
            )
            response = await model.generate_content_async(prompt)
            return response.text or ""
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return f"[LLM Error: {e}]"

    async def is_available(self) -> bool:
        return bool(self.api_key)


class OllamaProvider(LLMProvider):
    """Local Ollama LLM provider."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self.base_url = base_url or settings.ollama_base_url
        self.model = model or settings.ollama_model

    async def generate(self, prompt: str, system: str = "") -> str:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "system": system,
                        "stream": False,
                        "options": {
                            "num_predict": 1024,
                            "temperature": 0.2,
                        },
                    },
                )
                response.raise_for_status()
                return response.json().get("response", "")
        except Exception as e:
            logger.error(f"Ollama API error: {e}")
            return f"[LLM Error: {e}]"

    async def is_available(self) -> bool:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False


class FallbackProvider(LLMProvider):
    """Fallback provider that generates rule-based explanations without an LLM."""

    async def generate(self, prompt: str, system: str = "") -> str:
        return (
            "AI explanation unavailable — no LLM provider is configured. "
            "The impact analysis results above are based on static code analysis, "
            "dependency graph traversal, and semantic search. "
            "Configure an LLM provider (OpenAI, Gemini, or Ollama) in .env for "
            "AI-powered explanations."
        )

    async def is_available(self) -> bool:
        return True


def get_provider(provider_name: Optional[str] = None) -> LLMProvider:
    """Factory function to get the configured LLM provider.

    Falls back to FallbackProvider if no API keys are configured.
    """
    name = (provider_name or settings.llm_provider).lower()

    if name == "openai" and settings.openai_api_key:
        logger.info("Using OpenAI LLM provider")
        return OpenAIProvider()
    elif name == "gemini" and settings.gemini_api_key:
        logger.info("Using Gemini LLM provider")
        return GeminiProvider()
    elif name == "ollama":
        logger.info("Using Ollama LLM provider")
        return OllamaProvider()
    else:
        logger.warning(
            f"No valid LLM provider configured (requested: {name}). "
            "Using fallback provider."
        )
        return FallbackProvider()
