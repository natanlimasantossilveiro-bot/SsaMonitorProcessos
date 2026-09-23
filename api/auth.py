import os

from fastapi import Header, HTTPException, status
from dotenv import load_dotenv

load_dotenv()


def verificar_token(authorization: str = Header(default=None)) -> None:
    """
    Dependency do FastAPI: exige "Authorization: Bearer <API_INTERNAL_TOKEN>".

    Uso interno (Laravel → FastAPI) — não é autenticação de usuário final.
    """
    token_esperado = os.getenv("API_INTERNAL_TOKEN")

    if not token_esperado:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API_INTERNAL_TOKEN não configurado no servidor.",
        )

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autorização ausente.",
        )

    token_recebido = authorization.removeprefix("Bearer ").strip()

    if token_recebido != token_esperado:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token de autorização inválido.",
        )
