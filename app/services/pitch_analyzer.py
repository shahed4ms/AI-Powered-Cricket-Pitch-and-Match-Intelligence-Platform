import os

try:
    import cv2
    import numpy as np
except ImportError:  # pragma: no cover - dependency is declared in requirements.txt
    cv2 = None
    np = None
from flask import current_app


def analyze_pitch_image(image_path, api_key=None):
    if cv2 is None or np is None:
        return {"error": "Pitch prediction is currently unavailablegit status."}
    if not image_path or not os.path.isfile(image_path):
        current_app.logger.warning("Pitch analysis unavailable: image could not be read")
        return {"error": "Pitch image could not be read"}

    image = cv2.imread(image_path)
    if image is None:
        return {"error": "Pitch image could not be decoded"}

    height, width = image.shape[:2]
    # The central 80% avoids most sky, stands, and boundary advertising.
    crop = image[int(height * 0.1):int(height * 0.9), int(width * 0.1):int(width * 0.9)]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    green_mask = cv2.inRange(hsv, np.array([30, 35, 25]), np.array([95, 255, 230]))
    brown_mask = cv2.inRange(hsv, np.array([5, 35, 20]), np.array([30, 255, 220]))
    green_ratio = float(np.mean(green_mask > 0))
    brown_ratio = float(np.mean(brown_mask > 0))
    texture = float(np.std(gray))
    edges = cv2.Canny(gray, 60, 140)
    edge_ratio = float(np.mean(edges > 0))
    mean_brightness = float(np.mean(value))
    dark_ratio = float(np.mean(value < 65))
    crack_mask = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 5)
    crack_ratio = float(np.mean((crack_mask > 0) & (edges > 0)))

    if green_ratio >= 0.28 and brown_ratio >= 0.08:
        pitch_type = "sporting"
    elif green_ratio >= 0.22:
        pitch_type = "green"
    elif brown_ratio >= 0.32 and texture >= 35:
        pitch_type = "dusty"
    elif brown_ratio >= 0.18:
        pitch_type = "dry"
    elif texture < 22 and edge_ratio < 0.08:
        pitch_type = "dead"
    else:
        pitch_type = "unknown"

    bounce_percentage = int(np.clip(42 + texture * 0.8 + edge_ratio * 100, 10, 90))
    spin_percentage = int(np.clip(35 + brown_ratio * 80 + crack_ratio * 250, 10, 92))
    surface_condition = "cracked" if crack_ratio > 0.025 else "abrasive" if texture > 42 else "moist" if dark_ratio > 0.3 else "smooth"
    grass_coverage = "heavy" if green_ratio > 0.35 else "moderate" if green_ratio > 0.18 else "sparse" if green_ratio > 0.06 else "none"
    confidence = int(np.clip(45 + abs(green_ratio - brown_ratio) * 80 + min(texture, 60) * 0.35, 35, 88))

    return {
        "source": "opencv",
        "pitch_type": pitch_type,
        "bounce_estimate": "high" if bounce_percentage >= 68 else "medium" if bounce_percentage >= 42 else "low",
        "bounce_percentage": bounce_percentage,
        "spin_estimate": "high" if spin_percentage >= 68 else "medium" if spin_percentage >= 42 else "low",
        "spin_percentage": spin_percentage,
        "surface_condition": surface_condition,
        "grass_coverage": grass_coverage,
        "confidence": confidence,
        "metrics": {
            "green_ratio": round(green_ratio, 3),
            "brown_ratio": round(brown_ratio, 3),
            "texture": round(texture, 2),
            "edge_ratio": round(edge_ratio, 3),
            "crack_ratio": round(crack_ratio, 3),
        },
        "reasoning": (
            f"OpenCV measured {green_ratio:.0%} green coverage, {brown_ratio:.0%} brown soil, "
            f"texture {texture:.1f}, and edge density {edge_ratio:.1%}."
        ),
    }
