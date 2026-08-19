# Service CAPTCHA WURI — Prototype (Phase 1 / Phase 2)

Prototype du microservice CAPTCHA interne décrit dans le document de cadrage
« Étude et Conception d'un Système CAPTCHA Interne — Programme WURI ».

Ce prototype couvre :
- **Phase 1** : génération d'image de défi + validation locale.
- **Phase 2** : exposition via une API REST sécurisée (FastAPI), avec
  expiration des défis, usage unique, jeton de validation signé, et
  limitation de débit par IP.

## Installation

```bash
# Créer l'environnement virtuel
python3 -m venv venv

# L'activer
source venv/bin/activate      # Linux / macOS
venv\Scripts\activate         # Windows (PowerShell : venv\Scripts\Activate.ps1)

# Installer les dépendances à l'intérieur du venv
pip install -r requirements.txt
```

> Si `source` n'est pas reconnu (certains shells minimalistes type `sh`),
> appeler directement les binaires du venv sans l'activer :
> `venv/bin/pip install -r requirements.txt` puis
> `venv/bin/uvicorn app.main:app --reload --port 8000`.

> Le générateur d'image utilise la police système `DejaVu Sans Bold`
> (`/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf`), présente par
> défaut sur la plupart des distributions Linux. Adapter `FONT_PATH` dans
> `app/generator.py` si nécessaire sur un autre environnement.

## Lancer le service

```bash
# Une fois le venv activé :
uvicorn app.main:app --reload --port 8000
```

- Documentation interactive de l'API : http://127.0.0.1:8000/docs
- Page de démonstration : http://127.0.0.1:8000/demo/

## Lancer les tests

```bash
pytest tests/ -v
```

## Structure du projet

```
venv/              Environnement virtuel Python (généré, non versionné)
app/
  config.py       Paramètres (durées de vie, seuils anti-abus, secret de signature)
  generator.py     Génération de l'image du défi (texte + distorsion + bruit)
  security.py      Hachage de la réponse et jetons de validation signés (HMAC)
  store.py         Stockage en mémoire des défis (TTL, usage unique) + rate limiting
  main.py          API REST (FastAPI) : /captcha/generate, /captcha/verify
static/
  index.html       Page de démonstration consommant l'API
tests/
  test_captcha.py  Tests unitaires et bout-en-bout
```

## Utilisation par une application cliente

Le service est indépendant du langage de l'application appelante. Flux type :

```
1. GET  /captcha/generate
   -> { challenge_id, image_base64, expires_in }
   L'application affiche l'image et récupère la saisie de l'utilisateur.

2. POST /captcha/verify
   Corps : { "challenge_id": "...", "answer": "..." }
   -> { valid: true, validation_token: "..." }   si la réponse est correcte
   -> { valid: false }                            sinon

3. L'application inclut `validation_token` lors de la soumission finale
   de son propre formulaire métier, et vérifie sa signature/expiration
   côté serveur avant de traiter la demande (fonction
   `verify_validation_token` de app/security.py, à exposer si besoin sous
   forme d'un endpoint supplémentaire /captcha/check-token).
```

## Points volontairement simplifiés dans ce prototype (à traiter avant la Phase 3)

- **Stockage en mémoire** (`ChallengeStore`, `RateLimiter`) : ne fonctionne
  que pour une seule instance du service. À remplacer par Redis dès que
  plusieurs instances tournent derrière un répartiteur de charge.
- **`SIGNING_SECRET`** : valeur par défaut non sécurisée dans `config.py`,
  à définir obligatoirement via la variable d'environnement
  `WURI_CAPTCHA_SECRET` en dehors d'un usage local.
- **CORS ouvert (`allow_origins=["*"]`)** : à restreindre aux domaines des
  applications clientes réelles du programme.
- **HTTPS** : à assurer par le reverse proxy / la plateforme de déploiement,
  non géré par ce prototype exécuté en local.
- **Endpoint de vérification du jeton de validation** : la fonction existe
  (`security.verify_validation_token`) mais n'est pas encore exposée en
  tant qu'endpoint HTTP dédié — à ajouter selon les besoins des premières
  applications intégratrices (Phase 3).
