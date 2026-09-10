import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.config import settings

ROLE_CLAIM = "https://estacionamento.dom/role"

_jwks_client = PyJWKClient(f"https://{settings.auth0_domain}/.well-known/jwks.json") if settings.auth0_domain else None
_security = HTTPBearer()


def decode_token(token: str) -> dict:
    """Valida e decodifica um JWT do Auth0. Levanta jwt.PyJWTError em caso de falha."""
    if _jwks_client is None:
        raise RuntimeError("Auth0 não configurado no servidor.")

    signing_key = _jwks_client.get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=settings.auth0_audience,
        issuer=f"https://{settings.auth0_domain}/",
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
) -> dict:
    try:
        return decode_token(credentials.credentials)
    except RuntimeError:
        raise HTTPException(status_code=500, detail="Auth0 não configurado no servidor.")
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
