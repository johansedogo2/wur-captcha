"""
Service CAPTCHA WURI — API REST (prototype Phase 1/2).

Endpoints :
    GET  /captcha/generate  -> renvoie un identifiant de défi + l'image PNG (base64)
    POST /captcha/verify    -> vérifie une réponse, renvoie un jeton de validation
    GET  /health            -> sondage de disponibilité

Ce service est indépendant de toute application cliente : il est conçu pour
être appelé en HTTP par n'importe quelle application du programme WURI,
quel que soit son propre langage.
"""
from __future__ import annotations

import base64
import uuid

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import settings
from .generator import generate_challenge
from .security import hash_answer, issue_validation_token, verify_answer
from .store import ChallengeStore, RateLimiter

app = FastAPI(
    title="Service CAPTCHA WURI",
    description="Microservice interne de vérification humaine pour les applications du programme WURI.",
    version="0.1.0",
)

# CORS ouvert pour le prototype ; à restreindre aux domaines des applications
# clientes du programme avant tout déploiement au-delà d'un usage local.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if _STATIC_DIR.exists():
    app.mount("/demo", StaticFiles(directory=str(_STATIC_DIR), html=True), name="demo")

_challenge_store = ChallengeStore()
_generate_limiter = RateLimiter(settings.MAX_GENERATIONS_PER_WINDOW, settings.RATE_LIMIT_WINDOW_SECONDS)
_verify_limiter = RateLimiter(settings.MAX_VERIFY_ATTEMPTS_PER_WINDOW, settings.RATE_LIMIT_WINDOW_SECONDS)


def _client_key(request: Request) -> str:
    """Clé de limitation de débit basée sur l'adresse IP du client."""
    return request.client.host if request.client else "unknown"


class GenerateResponse(BaseModel):
    challenge_id: str
    image_base64: str = Field(description="Image PNG encodée en base64, prête pour un <img src='data:image/png;base64,...'>")
    expires_in: int


class VerifyRequest(BaseModel):
    challenge_id: str
    answer: str


class VerifyResponse(BaseModel):
    valid: bool
    validation_token: str | None = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/captcha/generate", response_model=GenerateResponse)
def generate(request: Request) -> GenerateResponse:
    if not _generate_limiter.allow(_client_key(request)):
        raise HTTPException(status_code=429, detail="Trop de défis générés depuis cette adresse. Réessayez plus tard.")

    challenge = generate_challenge()
    challenge_id = str(uuid.uuid4())
    answer_hash = hash_answer(challenge_id, challenge.text)
    _challenge_store.put(challenge_id, answer_hash, settings.CHALLENGE_TTL_SECONDS)

    return GenerateResponse(
        challenge_id=challenge_id,
        image_base64=base64.b64encode(challenge.image_bytes).decode("ascii"),
        expires_in=settings.CHALLENGE_TTL_SECONDS,
    )


@app.post("/captcha/verify", response_model=VerifyResponse)
def verify(payload: VerifyRequest, request: Request) -> VerifyResponse:
    if not _verify_limiter.allow(_client_key(request)):
        raise HTTPException(status_code=429, detail="Trop de tentatives depuis cette adresse. Réessayez plus tard.")

    stored_hash = _challenge_store.consume(payload.challenge_id)
    if stored_hash is None:
        # Défi inconnu, déjà utilisé, ou expiré : toujours invalide, sans distinction
        # (pour ne pas donner d'indice exploitable à un script d'attaque).
        return VerifyResponse(valid=False)

    if verify_answer(payload.challenge_id, payload.answer, stored_hash):
        token = issue_validation_token(payload.challenge_id)
        return VerifyResponse(valid=True, validation_token=token)

    return VerifyResponse(valid=False)
