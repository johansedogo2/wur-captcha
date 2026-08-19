"""
Tests du prototype : génération d'image, hachage/validation, usage unique,
expiration, et bout-en-bout via l'API FastAPI.
"""
import time

from fastapi.testclient import TestClient

from app.generator import generate_challenge
from app.security import hash_answer, verify_answer, issue_validation_token, verify_validation_token
from app.store import ChallengeStore, RateLimiter
from app.main import app

client = TestClient(app)


def test_generate_challenge_produces_valid_png():
    challenge = generate_challenge()
    assert len(challenge.text) == 5
    assert challenge.image_bytes[:8] == b"\x89PNG\r\n\x1a\n"  # signature PNG


def test_hash_answer_is_case_insensitive_and_trims_spaces():
    h1 = hash_answer("abc", "XY2Z9")
    h2 = hash_answer("abc", "  xy2z9  ")
    assert h1 == h2


def test_hash_answer_depends_on_challenge_id_salt():
    h1 = hash_answer("challenge-1", "XY2Z9")
    h2 = hash_answer("challenge-2", "XY2Z9")
    assert h1 != h2


def test_verify_answer_true_and_false_cases():
    stored = hash_answer("abc", "XY2Z9")
    assert verify_answer("abc", "xy2z9", stored) is True
    assert verify_answer("abc", "WRONG", stored) is False


def test_validation_token_roundtrip():
    token = issue_validation_token("abc")
    assert verify_validation_token(token) is True
    assert verify_validation_token(token + "tampered") is False
    assert verify_validation_token("not-a-token") is False


def test_challenge_store_single_use():
    store = ChallengeStore()
    store.put("id1", "hash1", ttl_seconds=60)
    assert store.consume("id1") == "hash1"
    # Deuxième consommation : le défi a déjà été utilisé -> None
    assert store.consume("id1") is None


def test_challenge_store_expiration():
    store = ChallengeStore()
    store.put("id1", "hash1", ttl_seconds=0)  # expire immédiatement
    time.sleep(0.05)
    assert store.consume("id1") is None


def test_rate_limiter_blocks_after_threshold():
    limiter = RateLimiter(max_events=3, window_seconds=60)
    key = "1.2.3.4"
    results = [limiter.allow(key) for _ in range(4)]
    assert results == [True, True, True, False]


def test_api_generate_returns_image_and_challenge_id():
    resp = client.get("/captcha/generate")
    assert resp.status_code == 200
    data = resp.json()
    assert "challenge_id" in data
    assert len(data["image_base64"]) > 100


def test_api_full_flow_wrong_then_correct_answer():
    # On ne connaît pas la réponse en clair via l'API (comportement voulu) :
    # on vérifie donc le flux via le store interne pour ce test bout-en-bout.
    from app.main import _challenge_store
    from app.generator import generate_challenge
    from app.security import hash_answer
    import uuid

    challenge = generate_challenge()
    challenge_id = str(uuid.uuid4())
    _challenge_store.put(challenge_id, hash_answer(challenge_id, challenge.text), ttl_seconds=60)

    # Mauvaise réponse : refusée, mais le défi est déjà consommé (usage unique)
    resp_wrong = client.post("/captcha/verify", json={"challenge_id": challenge_id, "answer": "WRONG"})
    assert resp_wrong.json()["valid"] is False

    # Rejouer le même challenge_id avec la bonne réponse doit échouer aussi
    # car le défi a été consommé dès la première tentative.
    resp_replay = client.post("/captcha/verify", json={"challenge_id": challenge_id, "answer": challenge.text})
    assert resp_replay.json()["valid"] is False


def test_api_verify_unknown_challenge_id():
    resp = client.post("/captcha/verify", json={"challenge_id": "does-not-exist", "answer": "ABCDE"})
    assert resp.status_code == 200
    assert resp.json()["valid"] is False
