"""Ollama LLM Service for Code Explanation and Debugging."""

from typing import Dict, Any, Optional
import httpx
from fastapi import HTTPException
from loguru import logger
from app.config import settings


class OllamaService:
    """Manages communication with the local Ollama LLM instance."""

    def __init__(self):
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_model
        self.timeout = settings.ollama_timeout_seconds

    async def check_health(self) -> Dict[str, Any]:
        """Check if Ollama is running and retrieve available models."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    data = res.json()
                    models = [m.get("name") for m in data.get("models", [])]
                    model_found = any(self.model in m or m in self.model for m in models)
                    return {
                        "available": True,
                        "configured_model": self.model,
                        "base_url": self.base_url,
                        "available_models": models,
                        "model_ready": model_found,
                    }
                return {
                    "available": False,
                    "configured_model": self.model,
                    "base_url": self.base_url,
                    "error": f"Ollama returned HTTP status {res.status_code}",
                }
        except httpx.ConnectError:
            return {
                "available": False,
                "configured_model": self.model,
                "base_url": self.base_url,
                "error": f"Cannot connect to Ollama at {self.base_url}. Please start Ollama.",
            }
        except Exception as e:
            return {
                "available": False,
                "configured_model": self.model,
                "base_url": self.base_url,
                "error": str(e),
            }

    def build_explain_prompt(
        self,
        file_path: str,
        code_content: str,
        question: str,
        rag_context: str,
    ) -> str:
        """Construct prompt for Code Explanation."""
        user_question = question.strip() if question and question.strip() else "Explain this code in detail."

        return f"""You are an expert AI Code Explanation Tutor.
You are explaining code from the repository file: `{file_path}`.

### USER QUESTION:
{user_question}

### RETRIEVED RELEVANT CODE CONTEXT (RAG from Repository):
{rag_context}

### CURRENT SELECTED FILE CODE (`{file_path}`):
```
{code_content}
```

Please provide a clear and structured explanation containing:
1. **What the code does** (High-level summary)
2. **Important functions/classes** (Key components and their roles)
3. **Main logic** (Step-by-step logic flow)
4. **Inputs** (Expected input parameters, data types, environment)
5. **Outputs** (Return values, produced side effects)
6. **Simple explanation** (Plain-English takeaway for easy understanding)

Format your response cleanly with clear headings."""

    def build_debug_prompt(
        self,
        file_path: str,
        code_content: str,
        user_query: str,
        rag_context: str,
    ) -> str:
        """Construct prompt for Debugger Bot."""
        debug_question = user_query.strip() if user_query and user_query.strip() else "Find errors and bugs in this code and provide a fix."

        return f"""You are an expert AI Software Debugger Bot.
Analyze the provided code from `{file_path}` along with the repository context to identify bugs, exceptions, syntax issues, or logic failures.

### USER DEBUG QUERY:
{debug_question}

### RETRIEVED RELEVANT CODE CONTEXT (RAG from Repository):
{rag_context}

### TARGET FILE CODE (`{file_path}`):
```
{code_content}
```

IMPORTANT: Do not claim code was executed unless execution results are explicitly provided. Analyze the code logically.

Provide your debugging analysis strictly following this format:

### Problem:
[Describe the bug, error, or failure in detail]

### Reason:
[Explain why this error occurs and root cause in the code/logic]

### Suggested Fix:
[Explain step-by-step how to resolve the issue]

### Corrected Code:
```
[Provide the complete corrected code]
```"""

    async def generate_response(self, prompt: str) -> str:
        """Send prompt to local Ollama and return the generated answer."""
        payload = {
            "model": self.model,
            "prompt": prompt,
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
                            f"Please run 'ollama pull {self.model}' or update OLLAMA_MODEL."
                        ),
                    )

                if res.status_code != 200:
                    raise HTTPException(
                        status_code=502,
                        detail=f"Ollama returned HTTP {res.status_code}: {res.text}",
                    )

                data = res.json()
                response_text = data.get("response", "").strip()
                if not response_text:
                    raise HTTPException(
                        status_code=500,
                        detail="Ollama returned an empty response.",
                    )
                return response_text

        except httpx.ConnectError:
            raise HTTPException(
                status_code=503,
                detail=f"Ollama is unavailable at {self.base_url}. Please ensure Ollama is running.",
            )
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=504,
                detail=f"Ollama timed out after {self.timeout}s while generating response.",
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Ollama error: {str(e)}",
            )


ollama_service = OllamaService()
