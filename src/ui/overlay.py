"""
On-screen overlay for the camera feed window.

Draws status indicators (live mode, microphone, distance, AI response)
on top of the video frame using OpenCV drawing functions.
"""

import cv2


def draw_overlay(
    frame,
    is_live_mode: bool,
    is_listening: bool,
    status_text: str,
    distance_cm: float | None,
) -> None:
    """
    Draw status information on the camera frame (in-place).

    Args:
        frame: OpenCV BGR image (modified in-place).
        is_live_mode: Whether continuous live analysis is active.
        is_listening: Whether the microphone is currently recording.
        status_text: Current status or last AI response (truncated).
        distance_cm: Ultrasonic sensor reading, or None if unavailable.
    """
    # Live mode indicator
    mode_color = (0, 0, 255) if is_live_mode else (0, 255, 0)
    mode_text = "LIVE: ON" if is_live_mode else "LIVE: OFF"
    cv2.putText(frame, mode_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, mode_color, 2)

    # Status text (last AI response)
    cv2.putText(frame, status_text, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    # Distance reading
    if distance_cm is not None:
        cv2.putText(
            frame,
            f"Distance: {distance_cm} cm",
            (10, 90),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 200, 0),
            2,
        )

    # Microphone indicator
    if is_listening:
        cv2.putText(
            frame,
            "MIC: LISTENING...",
            (10, 120),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 255),
            2,
        )
