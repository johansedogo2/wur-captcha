"""
Stockage temporaire en mémoire.

Pour le prototype (Phase 1 / Phase 2 locale), un simple dictionnaire protégé
par un verrou suffit. En production multi-instances (Phase 3+), ce module
sera remplacé par un backend partagé (Redis) sans changer l'interface
publique ci-dessous, ce qui isole le reste du service de ce choix.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass
class _ChallengeRecord:
    answer_hash: str
    expires_at: float
    consumed: bool = False


class ChallengeStore:
    """Associe un challenge_id à l'empreinte de sa réponse, avec expiration et usage unique."""

    def __init__(self) -> None:
        self._data: dict[str, _ChallengeRecord] = {}
        self._lock = threading.Lock()

    def put(self, challenge_id: str, answer_hash: str, ttl_seconds: int) -> None:
        with self._lock:
            self._data[challenge_id] = _ChallengeRecord(
                answer_hash=answer_hash,
                expires_at=time.time() + ttl_seconds,
            )

    def consume(self, challenge_id: str) -> str | None:
        """
        Récupère l'empreinte associée à un défi et le marque immédiatement
        comme consommé (usage unique), qu'il soit ensuite validé ou non.
        Retourne None si le défi est introuvable, expiré ou déjà consommé.
        """
        with self._lock:
            record = self._data.get(challenge_id)
            if record is None:
                return None
            if record.consumed or time.time() > record.expires_at:
                self._data.pop(challenge_id, None)
                return None
            record.consumed = True
            answer_hash = record.answer_hash
            # Le défi ne peut plus resservir, on le retire immédiatement.
            self._data.pop(challenge_id, None)
            return answer_hash

    def purge_expired(self) -> None:
        """Nettoyage périodique (à appeler depuis une tâche de fond)."""
        now = time.time()
        with self._lock:
            expired = [cid for cid, rec in self._data.items() if now > rec.expires_at]
            for cid in expired:
                self._data.pop(cid, None)


class RateLimiter:
    """Limiteur de débit simple par clé (ex. adresse IP), fenêtre glissante en mémoire."""

    def __init__(self, max_events: int, window_seconds: int) -> None:
        self._max_events = max_events
        self._window_seconds = window_seconds
        self._events: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            timestamps = [t for t in self._events.get(key, []) if now - t < self._window_seconds]
            if len(timestamps) >= self._max_events:
                self._events[key] = timestamps
                return False
            timestamps.append(now)
            self._events[key] = timestamps
            return True
