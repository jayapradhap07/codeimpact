"""Ollama LLM Service for Code Explanation, Debugging, and Q&A."""

import json
from typing import Dict, Any, Optional
import httpx
from fastapi import HTTPException
from app.config import settings


class OllamaService:
    """Manages communication with the local Ollama LLM instance."""

    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self.model = settings.OLLAMA_MODEL
        self.timeout = settings.OLLAMA_TIMEOUT_SECONDS

    async def check_health(self) -> Dict[str, Any]:
        """Check if Ollama is running and retrieve available models."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    data = res.json()
                    models = [m.get("name") for m in data.get("models", [])]
                    return {
                        "available": True,
                        "model": self.model,
                        "base_url": self.base_url,
                        "available_models": models,
                    }
                return {
                    "available": False,
                    "model": self.model,
                    "base_url": self.base_url,
                    "error": f"Ollama returned HTTP status {res.status_code}",
                }
        except httpx.ConnectError:
            return {
                "available": False,
                "model": self.model,
                "base_url": self.base_url,
                "error": "Cannot connect to Ollama. Make sure 'ollama serve' is running at "
                + self.base_url,
            }
        except Exception as e:
            return {
                "available": False,
                "model": self.model,
                "base_url": self.base_url,
                "error": str(e),
            }

    def build_prompt(
        self,
        code: str,
        language: str,
        mode: str,
        question: Optional[str],
        rag_context: str,
    ) -> str:
        """Construct a structured prompt based on the requested mode and RAG context."""
        mode_lower = mode.lower().strip()

        if mode_lower == "explain":
            return f"""You are an expert software developer and code explanation tutor.
Explain the following {language} code clearly for beginners and developers.

### RETRIEVED RELEVANT CODE CONTEXT (RAG):
{rag_context}

### FULL CODE:
```{language}
{code}
```

Please structure your explanation using the following format:
1. **Purpose**: What this code does at a high level.
2. **How It Works**: Step-by-step walkthrough of the logic.
3. **Important Functions / Classes**: Key components and their roles.
4. **Input & Output**: What data is expected and produced.
5. **Simple Summary**: Key takeaways in plain English.
"""

        elif mode_lower == "debug":
            return f"""You are a senior debugging assistant and software engineer.
Analyze the following {language} code to identify bugs, syntax issues, runtime errors, and logical mistakes.

### RETRIEVED RELEVANT CODE CONTEXT (RAG):
{rag_context}

### FULL CODE:
```{language}
{code}
```

Provide your debugging analysis strictly in this structured format:

### Problem:
[Describe the bug, syntax error, or logical issue clearly]

### Why it happens:
[Explain the underlying root cause]

### Suggested fix:
[Explain how to resolve the issue]

### Corrected code:
```{language}
[Provide the complete corrected code]
```
"""

        else:  # "ask" mode
            user_q = question if question else "Explain how this code works."
            return f"""You are an AI code assistant. Answer the user's question accurately based on the provided {language} code and retrieved context.

### USER QUESTION:
{user_q}

### RETRIEVED RELEVANT CODE CONTEXT (RAG):
{rag_context}

### FULL CODE:
```{language}
{code}
```

Provide a direct, concise, and helpful answer to the user's question, citing specific functions, lines, or logic where appropriate."""

    async def generate_response(
        self,
        code: str,
        language: str,
        mode: str,
        question: Optional[str],
        rag_context: str,
    ) -> str:
        """Send prompt to local Ollama and return the generated answer."""
        prompt = self.build_prompt(code, language, mode, question, rag_context)

        system_instruction = (
            "You are a helpful and accurate AI Code Explanation & Debugger Bot. "
            "Base your answer strictly on the provided code and retrieved context. "
            "Format your answer with clean Markdown headings, lists, and code blocks."
        )

        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_instruction,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "top_p": 0.9,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                )

                if res.status_code == 404:
                    raise HTTPException(
                        status_code=404,
                        detail=(
                            f"Model '{self.model}' not found in Ollama. "
                            f"Please run 'ollama pull {self.model}' or configure OLLAMA_MODEL in .env."
                        ),
                    )

                if res.status_code != 200:
                    raise HTTPException(
                        status_code=502,
                        detail=f"Ollama server returned error (HTTP {res.status_code}): {res.text}",
                    )

                data = res.json()
                response_text = data.get("response", "").strip()
                if not response_text:
                    raise HTTPException(
                        status_code=500,
                        detail="Ollama returned an empty response. Please try again.",
                    )
                return response_text

        except httpx.ConnectError:
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Ollama is unavailable at {self.base_url}. "
                    f"Please ensure Ollama is installed and running locally with 'ollama serve'."
                ),
            )
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=504,
                detail=(
                    f"Ollama timed out after {self.timeout}s while generating response. "
                    f"Consider using a smaller model or reducing input size."
                ),
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to communicate with Ollama: {str(e)}",
            )


ollama_service = OllamaService()
