# llm_client.py
from typing import Dict, Any, Optional
import json
import os
from dotenv import load_dotenv
load_dotenv()


class LLMClient:
    """Client for calling LLM (OpenAI)"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        """
        Initialize LLM client
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Model to use (default: gpt-4o)
        """
        from openai import OpenAI
        
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self._api_key:
            raise ValueError("OpenAI API key not provided and OPENAI_API_KEY env var not set")
        
        self._client = OpenAI(api_key=self._api_key)
        self._model = model
    
    async def call_llm(self, prompt: str) -> Dict[str, Any]:
        """
        Call LLM with prompt and return parsed JSON response + token usage
        
        Args:
            prompt: The prompt to send to LLM
            
        Returns:
            {
                "response": Dict (parsed JSON response from LLM),
                "usage": {
                    "input_tokens": int,
                    "output_tokens": int,
                    "total_tokens": int
                }
            }
        """
        try:
            response = self._client.responses.create(
                model=self._model,
                input=prompt,
            )
            
            # Extract text from response
            response_text = response.output_text
            
            # Parse JSON from response
            # Try to find JSON in the response (in case LLM adds extra text)
            response_text = response_text.strip()
            print(response_text)
            
            # Remove markdown code blocks if present
            if response_text.startswith("```json"):
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif response_text.startswith("```"):
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            # Parse JSON
            parsed_response = json.loads(response_text)
            
            # Extract token usage
            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.total_tokens
            }
            
            return {
                "response": parsed_response,
                "usage": usage
            }
            
        except json.JSONDecodeError as e:
            # NOTE: allow errors to return valid json
            print(f"Error parsing LLM response as JSON: {e}")
            print(f"Response text: {response_text}")
            raise ValueError(f"LLM did not return valid JSON: {e}")
        
        except Exception as e:
            print(f"Error calling LLM: {e}")
            raise




async def call_llm(prompt: str) -> Dict[str, Any]:
    """
    Convenience function to call LLM
    
    Args:
        prompt: The prompt to send to LLM
        
    Returns:
        {
            "response": Dict (parsed JSON response from LLM),
            "usage": {
                "input_tokens": int,
                "output_tokens": int,
                "total_tokens": int
            }
        }
    """
    client = LLMClient()
    return await client.call_llm(prompt)