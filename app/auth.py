import smtplib
import ssl
from email.message import EmailMessage
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import decode
from jwt.exceptions import InvalidTokenError
from pydantic import EmailStr, Field, SecretStr, TypeAdapter, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlmodel import select

from app.database import SessionDep
from app.models.user import Usuario


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", env_ignore_empty=True, hide_input_in_errors=True
    )

    auth_secret_key: SecretStr | None = Field(default=None, min_length=32)
    smtp_username: EmailStr | None = None
    smtp_password: SecretStr | None = None


config_auth = AuthSettings()
bearer = HTTPBearer(auto_error=False, bearerFormat="JWT", scheme_name="AcessoInsper")
validar_email = TypeAdapter(EmailStr)


def obter_chave() -> str:
    if config_auth.auth_secret_key is None:
        raise HTTPException(status_code=503, detail="A chave de autenticação não está configurada.")
    return config_auth.auth_secret_key.get_secret_value()


def enviar_codigo(email: str, codigo: str) -> None:
    if not config_auth.smtp_username or not config_auth.smtp_password:
        raise HTTPException(status_code=503, detail="O envio de e-mail não está configurado.")
    mensagem = EmailMessage()
    mensagem["Subject"] = "Seu código de acesso — Achados & Perdidos Insper"
    mensagem["From"] = config_auth.smtp_username
    mensagem["To"] = email
    mensagem.set_content(
        f"Seu código de acesso é: {codigo}\n\n"
        "Ele expira em 10 minutos e só pode ser usado uma vez.\n"
        "Se você não solicitou este acesso, ignore esta mensagem.\n"
    )
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(config_auth.smtp_username, config_auth.smtp_password.get_secret_value())
            smtp.send_message(mensagem)
    except OSError as error:
        raise HTTPException(status_code=503, detail="Não foi possível enviar o código. Tente novamente.") from error


def exigir_autenticacao(
    credenciais: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    session: SessionDep,
) -> Usuario:
    if credenciais is None:
        raise HTTPException(
            status_code=401, detail="Autenticação necessária.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    chave = obter_chave()
    try:
        claims = decode(
            credenciais.credentials,
            chave,
            algorithms=["HS256"],
            audience="achados-perdidos-api",
            issuer="achados-perdidos-insper",
            options={"require": ["sub", "exp", "iat", "nbf", "iss", "aud"], "strict_aud": True},
        )
        email = str(validar_email.validate_python(claims["sub"])).lower()
    except (InvalidTokenError, ValidationError) as error:
        raise HTTPException(
            status_code=401, detail="Token inválido ou expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    if email.rsplit("@", 1)[1] not in {"al.insper.edu.br", "insper.edu.br"}:
        raise HTTPException(status_code=403, detail="Use um e-mail institucional do Insper.")
    usuario = session.exec(select(Usuario).where(Usuario.email == email)).first()
    if usuario is None:
        raise HTTPException(
            status_code=401, detail="Usuário não cadastrado.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return usuario


UsuarioDep = Annotated[Usuario, Depends(exigir_autenticacao)]
