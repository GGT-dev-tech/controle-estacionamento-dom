import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.config import settings

ROLE_CLAIM = "https://estacionamento.dom/role"

_jwks_client = PyJWKClient(f"https://{settings.auth0_domain}/.well-known/jwks.json") if settings.auth0_domain else None
_security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
) -> dict:
    if _jwks_client is None:
        raise HTTPException(status_code=500, detail="Auth0 não configurado no servidor.")

    token = credentials.credentials
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.auth0_audience,
            issuer=f"https://{settings.auth0_domain}/",
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado. Faça login novamente.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido. Acesso negado.")


def require_role(*roles: str):
    """Dependência de RBAC — use como: Depends(require_role('admin'))"""

    async def checker(user: dict = Depends(get_current_user)) -> dict:
        user_role = user.get(ROLE_CLAIM, "operador")
        if user_role not in roles:
            raise HTTPException(status_code=403, detail="Permissão insuficiente.")
        return user

    return checker
