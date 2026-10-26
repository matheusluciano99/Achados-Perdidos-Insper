from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlmodel import select

from app.auth import UsuarioDep
from app.database import SessionDep, commit_or_conflict
from app.models.item import Item, ItemBase, ItemPublic

router = APIRouter(prefix="/itens", tags=["Itens"])


def get_item(
    id_item: Annotated[int, Path(gt=0, description="Identificador do item.")],
    session: SessionDep,
) -> Item:
    item = session.get(Item, id_item)
    if item is None:
        raise HTTPException(status_code=404, detail="Item não encontrado.")
    return item


ItemDep = Annotated[Item, Depends(get_item)]


@router.post(
    "",
    response_model=ItemPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar item encontrado",
)
def create_item(data: ItemBase, session: SessionDep, usuario: UsuarioDep) -> Item:
    item = Item.model_validate(data, update={"id_usuario": usuario.id})
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.get("", response_model=list[ItemPublic], summary="Listar itens encontrados")
def list_items(
    session: SessionDep,
    offset: Annotated[
        int, Query(alias="deslocamento", ge=0, description="Quantidade de itens a ignorar.")
    ] = 0,
    limit: Annotated[
        int, Query(alias="limite", ge=1, le=100, description="Quantidade máxima de itens.")
    ] = 100,
) -> Sequence[Item]:
    return session.exec(select(Item).order_by(Item.id).offset(offset).limit(limit)).all()


@router.get(
    "/{id_item}",
    response_model=ItemPublic,
    summary="Consultar item encontrado",
    responses={404: {"description": "Item não encontrado."}},
)
def read_item(item: ItemDep) -> Item:
    return item


@router.put(
    "/{id_item}",
    response_model=ItemPublic,
    summary="Atualizar todos os dados do item",
    responses={404: {"description": "Item não encontrado."}},
)
def update_item(data: ItemBase, item: ItemDep, session: SessionDep) -> Item:
    item.sqlmodel_update(data.model_dump())
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.delete(
    "/{id_item}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir item encontrado",
    responses={
        404: {"description": "Item não encontrado."},
        409: {"description": "O item possui uma retirada registrada."},
    },
)
def delete_item(item: ItemDep, session: SessionDep) -> Response:
    session.delete(item)
    commit_or_conflict(
        session, "O item possui uma retirada registrada. Exclua a retirada primeiro."
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
