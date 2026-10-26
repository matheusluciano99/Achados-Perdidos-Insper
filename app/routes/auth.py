import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Response
from jwt import encode
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app import auth
from app.database import SessionDep
from app.models.auth import (
    CodigoLogin,
    ConfirmacaoCodigo,
    SolicitacaoCodigo,
    TokenAcesso,
)
from app.models.user import Usuario

router = APIRouter(prefix="/auth", tags=["Autenticação"])


def hash_codigo(email: str, codigo: str, chave: str) -> str:
    return hmac.new(chave.encode(), f"{email}:{codigo}".encode(), hashlib.sha256).hexdigest()


@router.post("/solicitar-codigo", summary="Enviar código de acesso ao e-mail institucional")
def solicitar_codigo(data: SolicitacaoCodigo, session: SessionDep) -> dict[str, str]:
    chave = auth.obter_chave()
    agora = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
    codigo = f"{secrets.randbelow(1_000_000):06d}"
    existente = session.exec(select(CodigoLogin.email).where(CodigoLogin.email == data.email)).first()
    if existente is None:
        registro = CodigoLogin(
            email=data.email, codigo_hash=hash_codigo(data.email, codigo, chave),
            enviado_em=agora, expira_em=agora + timedelta(minutes=10),
        )
        session.add(registro)
        try:
            session.flush()
        except IntegrityError as error:
            session.rollback()
            raise HTTPException(status_code=429, detail="Aguarde antes de solicitar outro código.", headers={"Retry-After": "60"}) from error
    else:
        registro = session.exec(
            select(CodigoLogin).where(CodigoLogin.email == data.email).with_for_update()
        ).one()
        restante = 60 - int((agora - registro.enviado_em).total_seconds())
        if restante > 0:
            session.rollback()
            raise HTTPException(status_code=429, detail="Aguarde antes de solicitar outro código.", headers={"Retry-After": str(restante)})
        registro.codigo_hash = hash_codigo(data.email, codigo, chave)
        registro.enviado_em = agora
        registro.expira_em = agora + timedelta(minutes=10)
        registro.tentativas = 0
    try:
        auth.enviar_codigo(data.email, codigo)
    except HTTPException:
        session.rollback()
        raise
    session.commit()
    return {"mensagem": "Código enviado. Confira seu e-mail institucional."}


@router.post("/verificar-codigo", response_model=TokenAcesso, summary="Confirmar código e entrar na plataforma")
def verificar_codigo(data: ConfirmacaoCodigo, session: SessionDep, response: Response) -> TokenAcesso:
    chave = auth.obter_chave()
    registro = session.exec(
        select(CodigoLogin).where(CodigoLogin.email == data.email).with_for_update()
    ).first()
    # DATETIME no MySQL arredonda frações; truncar impede reuso no mesmo segundo.
    agora = datetime.now(UTC).replace(microsecond=0)
    if registro is None or registro.expira_em <= agora.replace(tzinfo=None) or registro.tentativas >= 5:
        session.rollback()
        raise HTTPException(status_code=401, detail="Código inválido ou expirado. Solicite um novo código.")
    if not hmac.compare_digest(registro.codigo_hash, hash_codigo(data.email, data.codigo, chave)):
        registro.tentativas += 1
        session.commit()
        raise HTTPException(status_code=401, detail="Código inválido ou expirado. Solicite um novo código.")
    usuario = session.exec(select(Usuario).where(Usuario.email == data.email)).first()
    if usuario is None:
        if data.nome is None:
            session.rollback()
            raise HTTPException(status_code=422, detail="Informe o nome no primeiro acesso.")
        usuario = Usuario.model_validate({"nome": data.nome, "email": data.email})
        session.add(usuario)
    registro.expira_em = agora.replace(tzinfo=None)
    expira_em = agora + timedelta(hours=1)
    token = encode(
        {"sub": data.email, "iss": "achados-perdidos-insper", "aud": "achados-perdidos-api", "iat": agora, "nbf": agora, "exp": expira_em},
        chave, algorithm="HS256",
    )
    session.commit()
    response.headers["Cache-Control"] = "no-store"
    return TokenAcesso(token_acesso=token, expira_em=expira_em)
