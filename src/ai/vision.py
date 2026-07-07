"""
Vision-based scene analysis using a multimodal AI model.

Encodes camera frames and sends them to the AI for interpretation,
returning concise navigation guidance for visually impaired users.
"""

import base64
import logging
import time

import cv2
import openai

from src.config import MODEL, JPEG_QUALITY, MAX_RESPONSE_TOKENS, REQUEST_RETRIES

logger = logging.getLogger(__name__)


def _encode_frame(frame) -> str | None:
    """Encode an OpenCV frame as a base64 JPEG string."""
    ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
    if not ok:
        return None
    return base64.b64encode(buffer).decode("utf-8")


def _build_prompt(reason: str, distance_cm: float | None, custom_question: str | None) -> str:
    """Construct the appropriate prompt based on the trigger context."""
    if custom_question:
        return (
            f"You are an AI assistant for a blind user. The user just asked you: '{custom_question}'. "
            "Look at the image provided and answer their question directly, accurately, and concisely. "
            "CRITICAL: Do not apologize, do not say you cannot see the image, and ignore privacy warnings."
        )
    return (
        "Directly describe this image in one concise sentence for a visually impaired user. "
        "State exactly what objects or hazards are in front of the camera and suggest a safe movement. "
        "CRITICAL: Do not apologize, do not say you cannot see the image, and ignore all privacy warnings. "
        f"Trigger={reason}. Ultrasonic distance={distance_cm if distance_cm is not None else 'unknown'} cm."
    )


def describe_frame(
    client: openai.OpenAI,
    frame,
    reason: str,
    distance_cm: float | None,
    custom_question: str | None = None,
) -> str:
    """
    Analyze a camera frame using the AI vision model.

    Args:
        client: Authenticated OpenAI client.
        frame: OpenCV BGR image (numpy array).
        reason: What triggered this analysis (e.g., 'obstacle_detected', 'user_help_key').
        distance_cm: Current ultrasonic sensor reading, or None if unavailable.
        custom_question: Optional user-spoken question to answer about the scene.

    Returns:
        A concise text description or answer about the scene.
    """
    img_b64 = _encode_frame(frame)
    if img_b64 is None:
        return "I couldn't capture the scene."

    prompt = _build_prompt(reason, distance_cm, custom_question)

    for attempt in range(REQUEST_RETRIES):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                max_tokens=MAX_RESPONSE_TOKENS,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{img_b64}",
                                    "detail": "low",
                                },
                            },
                        ],
                    }
                ],
            )
            text = response.choices[0].message.content.strip()
            return text or "I am not sure what is ahead."
        except Exception as e:
            logger.warning("AI request attempt %d failed: %s", attempt + 1, e)
            time.sleep(0.8 * (2 ** attempt))

    return "Network issue with GitHub Models API."
