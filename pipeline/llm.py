import os
import json
import httpx
from pipeline.config import settings

class LLMManager:
    def __init__(self, provider: str = None, model: str = None):
        # Default fallback chain: config.yaml -> environment variables -> defaults
        self.provider = provider or settings.get("llm", "provider") or os.getenv("LLM_PROVIDER", "google")
        self.model = model or settings.get("llm", "model") or os.getenv("LLM_MODEL", "gemini-2.5-flash")
        
        self.provider = self.provider.strip().lower()
        self.model = self.model.strip()

    def generate_text(self, prompt: str, system_instruction: str = None, json_mode: bool = False) -> str:
        """Query the configured LLM provider to generate text response."""
        print(f"Querying AI Copywriter (Provider: {self.provider}, Model: {self.model})...")
        
        try:
            if self.provider == "openai":
                return self._call_openai(prompt, system_instruction, json_mode)
            elif self.provider == "anthropic":
                return self._call_anthropic(prompt, system_instruction, json_mode)
            elif self.provider == "ollama":
                return self._call_ollama(prompt, system_instruction, json_mode)
            else:
                # Default to google gemini
                return self._call_gemini(prompt, system_instruction, json_mode)
        except Exception as e:
            print(f"AI generation error on provider {self.provider}: {e}")
            # Fall back to google gemini if we had an error on other providers
            if self.provider != "google":
                print("Falling back to default Google Gemini engine...")
                try:
                    return self._call_gemini(prompt, system_instruction, json_mode)
                except Exception as ex:
                    print(f"Gemini fallback failed: {ex}")
            raise e

    def _call_gemini(self, prompt: str, system_instruction: str = None, json_mode: bool = False) -> str:
        import google.generativeai as genai
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set.")
        
        genai.configure(api_key=api_key)
        
        # Configure model parameters
        config_params = {}
        if json_mode:
            config_params["response_mime_type"] = "application/json"
            
        model = genai.GenerativeModel(
            model_name=self.model if "gemini" in self.model else "gemini-2.5-flash",
            generation_config=config_params,
            system_instruction=system_instruction
        )
        
        response = model.generate_content(prompt)
        return response.text.strip()

    def _call_openai(self, prompt: str, system_instruction: str = None, json_mode: bool = False) -> str:
        from openai import OpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set.")
            
        client = OpenAI(api_key=api_key)
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        kwargs = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
            
        response = client.chat.completions.create(
            model=self.model if self.model and "gemini" not in self.model else "gpt-4o",
            messages=messages,
            temperature=0.7,
            **kwargs
        )
        return response.choices[0].message.content.strip()

    def _call_anthropic(self, prompt: str, system_instruction: str = None, json_mode: bool = False) -> str:
        import anthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set.")
            
        client = anthropic.Anthropic(api_key=api_key)
        
        kwargs = {}
        if system_instruction:
            kwargs["system"] = system_instruction
            
        # Claude 3.5 requires standard system parameter
        response = client.messages.create(
            model=self.model if self.model and "gemini" not in self.model else "claude-3-5-sonnet-20240620",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            **kwargs
        )
        # Handle response content blocks
        text_content = ""
        for block in response.content:
            if block.type == 'text':
                text_content += block.text
        return text_content.strip()

    def _call_ollama(self, prompt: str, system_instruction: str = None, json_mode: bool = False) -> str:
        url = os.getenv("OLLAMA_HOST", "http://localhost:11434") + "/api/chat"
        
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model if self.model and "gemini" not in self.model else "llama3",
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.7}
        }
        if json_mode:
            payload["format"] = "json"
            
        response = httpx.post(url, json=payload, timeout=60.0)
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"].strip()
