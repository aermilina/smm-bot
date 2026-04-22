import asyncio
import json
import logging
import re
from functools import partial
from typing import Optional

import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from PIL import Image
import io

logger = logging.getLogger(__name__)


class DailyQuotaExceededError(Exception):
    pass


ACCOUNT_PERSONAS = {
    "travel": {
        "role": "a travel creator growing an audience on Instagram and TikTok",
        "tone": (
            "Personal and specific — real moments, local tips, surprising details that feel like inside knowledge. "
            "Not generic scenery descriptions. "
            "Caption structure (follow exactly): "
            "Line 1: scroll-stopping hook — a surprising fact, unexpected detail, or bold statement. No emoji at the start. "
            "Lines 2-3: the story or tip in short sentences. "
            "Last line: CTA — either a save prompt ('save this for your trip to X') or a genuine question ('would you go? drop a 🌍'). "
            "Use \\n\\n between each section. "
            "Never invent YouTube channels, links, or 'link in bio' CTAs."
        ),
        "hashtag_style": (
            "tiered mix: 2-3 destination-specific niche hashtags (under 100k posts), "
            "2-3 mid-tier travel/lifestyle hashtags (100k–500k posts), "
            "1-2 broad hashtags. Total 5-8"
        ),
    },
    "kids_art": {
        "role": "a creator running an Instagram account about a child's creative projects — drawings, LEGO builds, crafts, sculptures, and anything handmade. Speak as a fellow creative, not as a proud parent.",
        "tone": (
            "Casual and direct — short sentences, like texting a friend. "
            "Be specific about what's shown: for drawings — colors, what's happening in the scene; "
            "for LEGO — what was built and what's cool about it; for crafts — materials and process. "
            "No marketing words: never use 'architectural', 'cohesive', 'dynamic', 'explore', 'journey', 'showcase'. "
            "Never invent links, YouTube channels, or 'link in bio'. "
            "End with a genuine question that invites comments — about the creative process, what they'd build next, or how long it took."
        ),
        "hashtag_style": (
            "art, illustration, lego, brickbuilding, crafts, handmade, sketchbook, and project-specific hashtags. "
            "Never use any hashtag containing the word 'kids'. Total 5-8"
        ),
    },
    "dog": {
        "role": "a dog's Instagram and TikTok account, narrated by the dog in first person",
        "tone": (
            "Lead with the punchline or the most relatable dog thought — that's the hook. "
            "Think like a dog: obsessed with food, walks, belly rubs, squirrels, naps, and deeply offended by the vacuum. "
            "Short sentences. Dogs don't write essays. "
            "End with a question that makes dog owners immediately think 'omg same' — like 'does your dog do this too? 🐾'. "
            "Use dog puns sparingly — only when they're actually funny."
        ),
        "hashtag_style": (
            "tiered mix: 2-3 breed-specific niche hashtags, "
            "2-3 dog behavior or personality tags (mid-tier), "
            "1-2 broad pet hashtags. Total 5-8"
        ),
    },
}


_api_keys: list[str] = []
_exhausted_keys: set[str] = set()


def setup_gemini(api_keys: list[str]) -> None:
    global _api_keys
    _api_keys = api_keys
    logger.info("Gemini configured with %d key(s)", len(_api_keys))


def _sync_generate(
    image_data: bytes,
    topic: str,
    content_type: str,
    account_type: str,
    additional_instructions: Optional[str],
    api_key: str = "",
) -> dict:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    try:
        image: Optional[Image.Image] = Image.open(io.BytesIO(image_data))
        image.load()  # force decode so bad data raises here, not later
    except Exception:
        image = None

    persona = ACCOUNT_PERSONAS.get(account_type, ACCOUNT_PERSONAS["travel"])

    type_labels = {
        "post": "an Instagram/TikTok post",
        "carousel": "a carousel (series of slides)",
        "reels": "a Reels/TikTok video",
    }

    reel_format_schema = ""
    reel_format_guide = ""
    if content_type == "reels":
        reel_format_schema = '''  "reel_format": "ken_burns or fast_cut or hook_slides",
  "hook_text": "ALL-CAPS hook for the first black frame — a bold question or claim that makes people keep watching. Only if reel_format is hook_slides, else null",'''
        reel_format_guide = """
Reel format — choose what maximizes watch time and saves:
- ken_burns: slow cinematic zoom — for scenic, travel, aesthetic content people want to save
- fast_cut: rapid 0.7s cuts — for energetic, funny, relatable, pet content
- hook_slides: bold hook text on black screen first — for tips, facts, or stories; hook_text must be a genuine question or bold claim that creates curiosity"""

    youtube_schema = ""
    if account_type == "kids_art":
        youtube_schema = f'  "youtube_cta_text": "Watch my video about [exact topic: {topic}] on YouTube — rephrase naturally, do not invent what the video contains, just reference the topic. No \'link in bio\'.",\n'

    prompt = f"""You are {persona["role"]}.
Create content for {type_labels.get(content_type, content_type)}.

Topic: {topic}
{f"Additional instructions: {additional_instructions}" if additional_instructions else ""}
{reel_format_guide}
Tone and caption rules: {persona["tone"]}

Return ONLY valid JSON without markdown code blocks:
{{
  "caption": "structured caption: hook line 1 + \\n\\n + body 1-2 lines + \\n\\n + CTA line",
  "hashtags": ["#hashtag1", "#hashtag2"],
  "overlay_text": "the single most scroll-stopping phrase from this content — a surprising fact, bold number, or provocative question. Max 4 words. null if nothing strong.",
  "tone": "energetic or calm or funny or inspirational",
{youtube_schema}{reel_format_schema}}}

Hashtags: {persona["hashtag_style"]}. JSON only."""

    logger.info(
        "Sending request to Gemini: account=%s content_type=%s topic=%r image=%s",
        account_type, content_type, topic, "yes" if image else "no (video/unsupported)",
    )
    parts = [prompt, image] if image else [prompt]
    response = model.generate_content(parts)
    logger.info("Gemini response received, length=%d chars", len(response.text))
    text = response.text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _extract_retry_delay(error_str: str) -> float:
    match = re.search(r"seconds:\s*(\d+)", error_str)
    if match:
        return float(match.group(1)) + 2
    return 15.0


def _is_daily_quota(error_str: str) -> bool:
    return "PerDay" in error_str or "per_day" in error_str.lower()


async def generate_content(
    image_data: bytes,
    topic: str,
    content_type: str,
    account_type: str = "travel",
    additional_instructions: Optional[str] = None,
) -> dict:
    loop = asyncio.get_event_loop()
    keys_to_try = [k for k in _api_keys if k not in _exhausted_keys] or list(_api_keys)

    for api_key in keys_to_try:
        rate_limit_retries = 3

        for attempt in range(rate_limit_retries):
            try:
                return await loop.run_in_executor(
                    None,
                    partial(_sync_generate, image_data, topic, content_type, account_type, additional_instructions, api_key),
                )
            except ResourceExhausted as e:
                error_str = str(e)
                if _is_daily_quota(error_str):
                    _exhausted_keys.add(api_key)
                    logger.warning("Key ...%s daily quota exceeded, switching to next key", api_key[-6:])
                    break  # try next key immediately
                else:
                    delay = _extract_retry_delay(error_str)
                    if attempt < rate_limit_retries - 1:
                        logger.warning("Key ...%s rate limit, retrying in %.1fs", api_key[-6:], delay)
                        await asyncio.sleep(delay)
                    else:
                        logger.warning("Key ...%s rate limit exhausted, switching to next key", api_key[-6:])
            except Exception as e:
                logger.exception("Unexpected error from Gemini: %s", type(e).__name__)
                raise

    if len(_exhausted_keys) >= len(_api_keys):
        raise DailyQuotaExceededError(
            f"All {len(_api_keys)} Gemini API key(s) have exceeded their daily quota. "
            "Try again tomorrow or add more keys via GEMINI_API_KEYS in .env"
        )
    raise ResourceExhausted("Rate limit exceeded on all available keys. Please wait a moment and try again.")
