"""
Configuration centralisée du service CAPTCHA WURI.

Toutes les valeurs sensibles (secret de signature des jetons) doivent être
surchargées via des variables d'environnement en production ; les valeurs
par défaut ci-dessous conviennent uniquement pour le prototype local.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # --- Génération du défi ---
    CHALLENGE_LENGTH: int = 5
    # Alphabet volontairement dépourvu de caractères ambigus (0/O, 1/l/I, etc.)
    CHALLENGE_ALPHABET: str = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
    IMAGE_WIDTH: int = 260
    IMAGE_HEIGHT: int = 90

    # --- Cycle de vie du défi ---
    CHALLENGE_TTL_SECONDS: int = 180          # 3 minutes
    VALIDATION_TOKEN_TTL_SECONDS: int = 300    # 5 minutes

    # --- Anti-abus ---
    MAX_GENERATIONS_PER_WINDOW: int = 20       # par IP
    MAX_VERIFY_ATTEMPTS_PER_WINDOW: int = 10   # par IP
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # --- Sécurité ---
    # En production : charger depuis une variable d'environnement / un secret manager.
    SIGNING_SECRET: str = os.environ.get("WURI_CAPTCHA_SECRET", "change-me-in-production")


settings = Settings()
