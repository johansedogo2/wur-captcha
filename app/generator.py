"""
Génération du défi CAPTCHA : texte aléatoire + image déformée.

Approche volontairement simple et sans dépendance externe lourde :
- texte aléatoire cryptographiquement sûr (module `secrets`) ;
- rendu image avec rotation/translation aléatoire de chaque caractère,
  lignes parasites et bruit ponctuel pour gêner l'OCR automatisé.
"""
from __future__ import annotations

import io
import secrets
from dataclasses import dataclass
from pathlib import Path
from random import Random

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from .config import settings

# Police embarquée dans le projet : garantit un fonctionnement identique sur
# Linux, macOS et Windows, sans dépendre d'une police système préinstallée.
_ASSETS_DIR = Path(__file__).resolve().parent / "assets"
_BUNDLED_FONT = _ASSETS_DIR / "DejaVuSans-Bold.ttf"

# Chemins de repli si jamais la police embarquée est absente (ne devrait pas arriver).
_FALLBACK_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",       # Linux (Debian/Ubuntu)
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",           # macOS
    "C:\\Windows\\Fonts\\arialbd.ttf",                              # Windows
]

FONT_SIZE = 42


def _load_font() -> ImageFont.FreeTypeFont:
    """Charge la police embarquée, avec repli sur des polices système connues."""
    candidates = [str(_BUNDLED_FONT), *_FALLBACK_FONT_PATHS]
    for path in candidates:
        try:
            return ImageFont.truetype(path, FONT_SIZE)
        except OSError:
            continue
    # Dernier recours : police bitmap par défaut de Pillow (moins esthétique
    # mais garantit que le service ne plante jamais faute de police).
    return ImageFont.load_default(size=FONT_SIZE)


@dataclass(frozen=True)
class Challenge:
    text: str          # réponse attendue (jamais transmise au client autrement que dans l'image)
    image_bytes: bytes  # image PNG du défi


def _random_text() -> str:
    """Génère une chaîne aléatoire à partir d'un générateur cryptographiquement sûr."""
    alphabet = settings.CHALLENGE_ALPHABET
    return "".join(secrets.choice(alphabet) for _ in range(settings.CHALLENGE_LENGTH))


def _noisy_background(draw: ImageDraw.ImageDraw, w: int, h: int, rng: Random) -> None:
    """Ajoute des lignes parasites et un bruit ponctuel en arrière-plan."""
    for _ in range(6):
        x1, y1 = rng.randint(0, w), rng.randint(0, h)
        x2, y2 = rng.randint(0, w), rng.randint(0, h)
        color = tuple(rng.randint(140, 200) for _ in range(3))
        draw.line((x1, y1, x2, y2), fill=color, width=1)
    for _ in range(w * h // 25):
        x, y = rng.randint(0, w - 1), rng.randint(0, h - 1)
        color = tuple(rng.randint(150, 210) for _ in range(3))
        draw.point((x, y), fill=color)


def render_challenge_image(text: str, seed: int | None = None) -> bytes:
    """Construit l'image PNG du défi à partir du texte attendu."""
    rng = Random(seed)
    w, h = settings.IMAGE_WIDTH, settings.IMAGE_HEIGHT

    base = Image.new("RGB", (w, h), color=(255, 255, 255))
    draw = ImageDraw.Draw(base)
    _noisy_background(draw, w, h, rng)

    font = _load_font()

    # Chaque caractère est dessiné séparément sur un calque, tourné puis collé
    # à une position légèrement aléatoire pour casser la régularité du texte.
    char_spacing = w // (len(text) + 1)
    for i, ch in enumerate(text):
        char_img = Image.new("RGBA", (60, 60), (255, 255, 255, 0))
        char_draw = ImageDraw.Draw(char_img)
        color = (rng.randint(20, 90), rng.randint(20, 90), rng.randint(20, 90))
        char_draw.text((10, 5), ch, font=font, fill=color)
        angle = rng.uniform(-28, 28)
        rotated = char_img.rotate(angle, resample=Image.BICUBIC, expand=True)

        x = char_spacing * i + rng.randint(-4, 4) + 10
        y = rng.randint(5, 20)
        base.paste(rotated, (x, y), rotated)

    base = base.filter(ImageFilter.SMOOTH)

    buffer = io.BytesIO()
    base.save(buffer, format="PNG")
    return buffer.getvalue()


def generate_challenge() -> Challenge:
    """Génère un nouveau défi complet (texte + image)."""
    text = _random_text()
    image_bytes = render_challenge_image(text)
    return Challenge(text=text, image_bytes=image_bytes)
