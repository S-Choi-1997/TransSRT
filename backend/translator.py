"""
Translator Module
Integrates with Gemini API for async batch translation of subtitles.
Uses REST API for Cloud Run compatibility.
"""

import asyncio
import os
import json
from typing import List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import requests

from chunker import Chunk


class TranslationError(Exception):
    """Custom exception for translation errors."""
    pass


class RateLimitError(Exception):
    """Exception for rate limit errors."""
    pass


class GeminiTranslator:
    """Translator using Google Gemini REST API with async batch processing."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-1.5-flash",
        max_concurrent: int = 10
    ):
        """
        Initialize Gemini translator.

        Args:
            api_key: Google Gemini API key
            model: Gemini model name (default: gemini-1.5-flash)
            max_concurrent: Maximum concurrent API requests (default: 10)
        """
        self.api_key = api_key.strip()  # Remove any whitespace/newlines
        self.model_name = model
        self.max_concurrent = max_concurrent

        # REST API endpoint
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

        # Semaphore for rate limiting
        self.semaphore = asyncio.Semaphore(max_concurrent)

    def _create_prompt(self, chunk: Chunk) -> str:
        """
        Create translation prompt for a chunk.

        Args:
            chunk: Chunk object containing entries to translate

        Returns:
            Formatted prompt string

        Note: This is a basic prompt structure. Will be optimized collaboratively.
        """
        # Optimized prompt for tarot reading YouTube content
        prompt = """You are a professional translator and an expert in English-speaking Tarot YouTube content. Please translate the provided Korean Tarot script into natural, conversational, and "vibe-focused" English.

CRITICAL REQUIREMENTS:
1. You MUST translate EXACTLY {count} Korean subtitles
2. Each input line MUST have EXACTLY ONE corresponding output line
3. Output format: NUMBER. TRANSLATION (e.g., "1. Hi guys,")
4. NEVER skip, merge, or split entries
5. Preserve line breaks within each subtitle text exactly as they appear in the Korean

BRAND & STYLE GUIDELINES:
- Always translate '컴포타로' as "Comfortarot" (not "Compo Tarot")
- Use a warm, intuitive, and comforting tone
- Use spiritual phrasing like: "I'm picking up on...", "The cards are showing...", "There's a strong energy of...", "It feels like..."
- Include natural filler words like "Honestly," "Actually," "It's like," to sound like a human reader

ADDRESSING THE AUDIENCE - CRITICAL RULE:
- Address the viewer as "you" or "your" in a 1-on-1 conversation style
- When translating "1번 분들", "2번 분들", "X번을 뽑으신 분들":
  * If it appears with a greeting word (안녕하세요, 어서오세요, 환영합니다) in the SAME sentence → translate the greeting naturally
  * In ALL other cases → translate as "you" or "your"
- Examples of correct translations:
  * "1번 분들은" → "You are"
  * "2번 선택하신 분들" → "You"
  * "3번 카드 분들이" → "You"

RELATIONSHIP TERMINOLOGY:
- For '상대방', '상대방 분': Use "they" or "them" as the default pronoun
- If the context clearly refers to reconciliation/past relationship (재회), use "your ex"
- Only use "your person" if the context is about a current relationship or attraction

TRANSLATION EXAMPLES:
1. 안녕하세요 → Hi guys,
2. 1번 카드 뽑아주신 분들 어서오세요 → Welcome to those who chose card 1! (has greeting)
3. 1번 분들은 → You are
4. 1번 분들을 기다리시는 → I know you're waiting
5. 4번 분들이 직접 연락하면 → If you reach out directly
6. 2번 선택하신 분들 기다리고 계시죠 → You've been waiting, haven't you?
7. 3번 선택하신 분들 상대방이 → They
8. 1번 분들 지금 힘드시죠 → You're having a hard time right now, aren't you?
9. 2번 분들 상대방 분은 → They are
10. 상대방이 연락을 → They will reach out
11. 재회 가능성이 → The chances of reconciliation / Your ex coming back

"""

        # Add context if available
        if chunk.previous_context:
            prompt += f"CONTEXT (previous subtitles for continuity):\n"
            for i, entry in enumerate(chunk.previous_context[-3:], 1):
                prompt += f"  {entry.text}\n"
            prompt += "\n"

        # Add current chunk info
        prompt += f"CHUNK INFO: This is chunk {chunk.index}/{chunk.total}\n\n"
        prompt += f"TRANSLATE THESE {len(chunk.entries)} KOREAN SUBTITLES:\n\n"

        for i, entry in enumerate(chunk.entries, 1):
            prompt += f"{i}. {entry.text}\n"

        prompt += f"\n"
        prompt += f"OUTPUT FORMAT (EXACTLY {len(chunk.entries)} LINES):\n"
        prompt += f"1. [English translation of line 1]\n"
        prompt += f"2. [English translation of line 2]\n"
        prompt += f"...\n"
        prompt += f"{len(chunk.entries)}. [English translation of line {len(chunk.entries)}]\n"
        prompt += f"\nREMEMBER: Output MUST contain EXACTLY {len(chunk.entries)} numbered lines. No more, no less."

        return prompt.replace("{count}", str(len(chunk.entries)))

    def _parse_response(self, response_text: str, expected_count: int) -> List[str]:
        """
        Parse Gemini API response into list of translations.

        Args:
            response_text: Raw response from Gemini
            expected_count: Expected number of translations

        Returns:
            List of translated subtitle texts

        Raises:
            TranslationError: If response cannot be parsed correctly
        """
        import re
        import logging
        logger = logging.getLogger(__name__)

        # Split by newlines and clean
        lines = [line.strip() for line in response_text.strip().split('\n') if line.strip()]

        # Log raw response for debugging
        logger.info(f"Parsing response: {len(lines)} non-empty lines (expected {expected_count})")

        # Parse numbered lines in format "N. translation"
        translations = {}
        for line in lines:
            # Match pattern: number followed by . or ) then text
            match = re.match(r'^(\d+)[\.\)]\s*(.+)$', line)
            if match:
                num = int(match.group(1))
                text = match.group(2).strip()
                if 1 <= num <= expected_count:
                    translations[num] = text
                else:
                    logger.warning(f"Ignoring line with out-of-range number {num}: {line[:50]}...")
            else:
                # Skip lines that don't match numbered format (could be extra text from model)
                logger.warning(f"Ignoring non-numbered line: {line[:50]}...")

        # Verify we have all translations
        if len(translations) != expected_count:
            missing = [i for i in range(1, expected_count + 1) if i not in translations]
            found = sorted(translations.keys())
            error_msg = f"Expected {expected_count} translations, got {len(translations)}. "
            if missing:
                error_msg += f"Missing numbers: {missing[:10]}. "
            error_msg += f"Found numbers: {found[:10] if len(found) > 10 else found}"
            logger.error(f"Parsing failed: {error_msg}")
            logger.error(f"Raw response preview: {response_text[:500]}...")
            raise TranslationError(error_msg)

        # Return translations in order
        ordered_translations = [translations[i] for i in range(1, expected_count + 1)]
        logger.info(f"Successfully parsed {len(ordered_translations)} translations")

        return ordered_translations

    def _call_gemini_rest(self, prompt: str) -> str:
        """
        Call Gemini REST API directly.

        Args:
            prompt: Translation prompt

        Returns:
            Response text from Gemini

        Raises:
            TranslationError: If API call fails
        """
        url = f"{self.base_url}/models/{self.model_name}:generateContent"

        headers = {
            "Content-Type": "application/json"
        }

        params = {
            "key": self.api_key
        }

        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ]
        }

        try:
            response = requests.post(
                url,
                headers=headers,
                params=params,
                json=payload,
                timeout=120  # 120 second timeout for longer chunks
            )
            response.raise_for_status()

            result = response.json()

            # Extract text from response
            if 'candidates' not in result or len(result['candidates']) == 0:
                raise TranslationError("No candidates in response")

            candidate = result['candidates'][0]
            if 'content' not in candidate or 'parts' not in candidate['content']:
                raise TranslationError("Invalid response structure")

            parts = candidate['content']['parts']
            if len(parts) == 0 or 'text' not in parts[0]:
                raise TranslationError("No text in response")

            return parts[0]['text']

        except requests.exceptions.Timeout:
            raise asyncio.TimeoutError("Request timed out")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                raise RateLimitError(f"Rate limit exceeded: {e}")
            else:
                raise TranslationError(f"HTTP error: {e}")
        except Exception as e:
            raise TranslationError(f"API call failed: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((asyncio.TimeoutError, RateLimitError))
    )
    async def _translate_chunk_with_retry(self, chunk: Chunk) -> List[str]:
        """
        Translate a single chunk with retry logic.

        Args:
            chunk: Chunk to translate

        Returns:
            List of translated texts

        Raises:
            TranslationError: If translation fails after retries
        """
        import time
        import logging
        logger = logging.getLogger(__name__)

        async with self.semaphore:
            start_time = time.time()
            try:
                logger.info(f"[Chunk {chunk.index}/{chunk.total}] Starting translation...")

                prompt_start = time.time()
                prompt = self._create_prompt(chunk)
                prompt_time = time.time() - prompt_start
                logger.info(f"[Chunk {chunk.index}/{chunk.total}] Prompt created in {prompt_time:.2f}s")

                # Call REST API (sync call, wrapped in async context)
                api_start = time.time()
                loop = asyncio.get_event_loop()
                response_text = await loop.run_in_executor(
                    None,
                    lambda: self._call_gemini_rest(prompt)
                )
                api_time = time.time() - api_start
                logger.info(f"[Chunk {chunk.index}/{chunk.total}] API call completed in {api_time:.2f}s")

                # Check for empty response
                if not response_text:
                    raise TranslationError("Empty response from Gemini API")

                # Parse response
                parse_start = time.time()
                translations = self._parse_response(response_text, len(chunk.entries))
                parse_time = time.time() - parse_start

                total_time = time.time() - start_time
                logger.info(f"[Chunk {chunk.index}/{chunk.total}] Parsing completed in {parse_time:.2f}s")
                logger.info(f"[Chunk {chunk.index}/{chunk.total}] TOTAL TIME: {total_time:.2f}s")

                return translations

            except TranslationError as e:
                # Parsing/translation errors - don't retry, fail immediately
                total_time = time.time() - start_time
                logger.error(f"[Chunk {chunk.index}/{chunk.total}] Translation error (no retry) after {total_time:.2f}s: {e}")
                raise  # Don't retry translation errors
            except (asyncio.TimeoutError, RateLimitError) as e:
                # Network/rate limit errors - retry
                total_time = time.time() - start_time
                logger.error(f"[Chunk {chunk.index}/{chunk.total}] Retryable error after {total_time:.2f}s: {e}")
                raise  # Let retry decorator handle these
            except Exception as e:
                total_time = time.time() - start_time
                logger.error(f"[Chunk {chunk.index}/{chunk.total}] Unexpected error after {total_time:.2f}s: {e}")
                raise TranslationError(f"Translation failed: {e}")

    async def translate_chunks_async(self, chunks: List[Chunk]) -> List[List[str]]:
        """
        Translate multiple chunks in parallel with rate limiting.

        Args:
            chunks: List of Chunk objects to translate

        Returns:
            List of translation lists (one list per chunk)

        Raises:
            TranslationError: If any chunk translation fails completely
        """
        import time
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f"========== TRANSLATION START ==========")
        logger.info(f"Total chunks: {len(chunks)}")
        logger.info(f"Max concurrent requests: {self.max_concurrent}")
        logger.info(f"Model: {self.model_name}")
        start_time = time.time()

        tasks = [self._translate_chunk_with_retry(chunk) for chunk in chunks]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        total_time = time.time() - start_time

        # Calculate detailed timing statistics
        total_entries = sum(len(chunk.entries) for chunk in chunks)
        avg_per_chunk = total_time / len(chunks)
        avg_per_entry = total_time / total_entries if total_entries > 0 else 0

        logger.info(f"========== TRANSLATION COMPLETE ==========")
        logger.info(f"Total time: {total_time:.2f}s")
        logger.info(f"Total entries: {total_entries}")
        logger.info(f"Average per chunk: {avg_per_chunk:.2f}s")
        logger.info(f"Average per entry: {avg_per_entry:.3f}s")
        logger.info(f"Throughput: {total_entries/total_time:.2f} entries/sec")

        # Handle results
        translations = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                raise TranslationError(
                    f"Chunk {i+1}/{len(chunks)} failed: {result}"
                )
            translations.append(result)

        return translations

    def translate_chunks(self, chunks: List[Chunk]) -> List[List[str]]:
        """
        Synchronous wrapper for async translation.

        Args:
            chunks: List of Chunk objects to translate

        Returns:
            List of translation lists (one list per chunk)
        """
        return asyncio.run(self.translate_chunks_async(chunks))


def translate_subtitles(
    chunks: List[Chunk],
    api_key: str,
    model: str = "gemini-1.5-flash",
    max_concurrent: int = 10
) -> List[List[str]]:
    """
    Convenience function to translate subtitle chunks.

    Args:
        chunks: List of Chunk objects
        api_key: Gemini API key
        model: Model name (default: gemini-1.5-flash)
        max_concurrent: Max concurrent requests (default: 10)

    Returns:
        List of translation lists
    """
    translator = GeminiTranslator(
        api_key=api_key,
        model=model,
        max_concurrent=max_concurrent
    )
    return translator.translate_chunks(chunks)
