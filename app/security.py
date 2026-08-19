"""
Primitives de sécurité : hachage des réponses et jetons de validation signés.

Principe : la réponse en clair n'est JAMAIS conservée côté serveur.
Seule une empreinte salée est stockée, comparée en temps constant.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time

from .config import settings


def hash_answer(challenge_id: str, answer: str) -> str:
    """
    Empreinte de la réponse attendue.

    Le `challenge_id` sert de sel : deux défis différents avec la même
    réponse textuelle produisent des empreintes différentes.
    """
    normalized = answer.strip().upper()
    payload = f"{challenge_id}:{normalized}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def verify_answer(challenge_id: str, submitted_answer: str, stored_hash: str) -> bool:
    """Compare la réponse soumise à l'empreinte stockée, en temps constant."""
    candidate_hash = hash_answer(challenge_id, submitted_answer)
    return hmac.compare_digest(candidate_hash, stored_hash)


def issue_validation_token(challenge_id: str) -> str:
    """
    Émet un jeton signé attestant qu'un défi a été résolu avec succès.

    Format : <random>.<expiry>.<signature>
    Le jeton est à usage unique : sa consommation est gérée par le store,
    pas par le jeton lui-même.
    """
    nonce = secrets.token_urlsafe(16)
    expiry = int(time.time()) + settings.VALIDATION_TOKEN_TTL_SECONDS
    message = f"{nonce}.{expiry}".encode("utf-8")
    signature = hmac.new(settings.SIGNING_SECRET.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return f"{nonce}.{expiry}.{signature}"


def verify_validation_token(token: str) -> bool:
    """Vérifie la signature et l'expiration d'un jeton de validation."""
    try:
        nonce, expiry_str, signature = token.split(".")
        expiry = int(expiry_str)
    except (ValueError, AttributeError):
        return False

    if time.time() > expiry:
        return False

    message = f"{nonce}.{expiry}".encode("utf-8")
    expected_signature = hmac.new(
        settings.SIGNING_SECRET.encode("utf-8"), message, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected_signature)
