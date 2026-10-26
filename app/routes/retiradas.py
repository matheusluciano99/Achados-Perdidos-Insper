from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlmodel import select

from app.auth import UsuarioDep
from app.database import SessionDep, commit_or_conflict
from app.models.retirada import Retirada, RetiradaBase, RetiradaPublica
from app.models.item import Item


router = APIRouter(prefix="/retiradas", tags=["Retiradas"])


def get_retirada(
    id_retirada: Annotated[int, Path(gt=0, description="Identificador da retirada.")],
    session: SessionDep,
) -> Retirada:
    retirada = session.get(Retirada, id_retirada)
    if retirada is None:
        raise HTTPException(status_code=404, detail="Retirada não encontrada.")
    return retirada


RetiradaDep = Annotated[Retirada, Depends(get_retirada)]


@router.post(
    "",
    response_model=RetiradaPublica,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar retirada de item",
    responses={
        404: {"description": "Item não encontrado."},
        409: {"description": "O item já possui retirada ou não está mais disponível."},
    },
)
def create_retirada(data: RetiradaBase, session: SessionDep, usuario: UsuarioDep) -> Retirada:
    if session.get(Item, data.id_item) is None:
        raise HTTPException(status_code=404, detail="Item não encontrado.")
    retirada = Retirada.model_validate(data, update={"id_usuario": usuario.id})
    session.add(retirada)
    commit_or_conflict(session, "O item já possui retirada ou não está mais disponível.")
    session.refresh(retirada)
    return retirada


@router.get("", response_model=list[RetiradaPublica], summary="Listar retiradas")
def list_retiradas(
    session: SessionDep,
    offset: Annotated[
        int, Query(alias="deslocamento", ge=0, description="Quantidade de retiradas a ignorar.")
    ] = 0,
    limit: Annotated[
        int, Query(alias="limite", ge=1, le=100, description="Quantidade máxima de retiradas.")
    ] = 100,
) -> Sequence[Retirada]:
    return session.exec(
        select(Retirada).order_by(Retirada.id).offset(offset).limit(limit)
    ).all()


@router.get(
    "/{id_retirada}",
    response_model=RetiradaPublica,
    summary="Consultar retirada",
    responses={404: {"description": "Retirada não encontrada."}},
)
def read_retirada(retirada: RetiradaDep) -> Retirada:
    return retirada


@router.put(
    "/{id_retirada}",
    response_model=RetiradaPublica,
    summary="Atualizar todos os dados da retirada",
    responses={
        404: {"description": "Retirada ou item não encontrado."},
        409: {"description": "O item já possui retirada ou não está mais disponível."},
    },
)
def update_retirada(
    data: RetiradaBase, retirada: RetiradaDep, session: SessionDep
) -> Retirada:
    if session.get(Item, data.id_item) is None:
        raise HTTPException(status_code=404, detail="Item não encontrado.")
    retirada.sqlmodel_update(data.model_dump())
    session.add(retirada)
    commit_or_conflict(session, "O item já possui retirada ou não está mais disponível.")
    session.refresh(retirada)
    return retirada


@router.delete(
    "/{id_retirada}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir retirada",
    responses={404: {"description": "Retirada não encontrada."}},
)
def delete_retirada(retirada: RetiradaDep, session: SessionDep) -> Response:
    session.delete(retirada)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
