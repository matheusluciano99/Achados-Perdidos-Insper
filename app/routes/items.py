from collections.abc import Sequence
from io import BytesIO
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    Response,
    UploadFile,
    status,
)
from PIL import Image, ImageOps
from sqlmodel import select

from app.auth import UsuarioDep
from app.database import SessionDep, commit_or_conflict
from app.models.item import Item, ItemBase, ItemCreate, ItemPublic
from app.models.photo import FotoItem

router = APIRouter(prefix="/itens", tags=["Itens"])
MAX_FOTO_BYTES = 5 * 1024 * 1024
MAX_FOTO_PIXELS = 20_000_000


def preparar_foto(foto: UploadFile) -> bytes:
    conteudo = foto.file.read(MAX_FOTO_BYTES + 1)
    if len(conteudo) > MAX_FOTO_BYTES:
        raise HTTPException(status_code=413, detail="A foto deve ter até 5 MB.")
    try:
        with Image.open(BytesIO(conteudo), formats=("JPEG", "PNG")) as imagem:
            if imagem.width * imagem.height > MAX_FOTO_PIXELS:
                raise HTTPException(status_code=413, detail="A foto deve ter até 20 megapixels.")
            imagem = ImageOps.exif_transpose(imagem).convert("RGB")
            imagem.thumbnail((1920, 1920))
            saida = BytesIO()
            imagem.save(saida, format="JPEG", quality=85)
            return saida.getvalue()
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as error:
        raise HTTPException(status_code=400, detail="Envie uma imagem JPEG ou PNG válida.") from error


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
    summary="Cadastrar item encontrado com foto",
    responses={
        400: {"description": "Imagem inválida."},
        413: {"description": "Imagem excede o tamanho ou a resolução permitida."},
        409: {"description": "Não foi possível cadastrar o item com a foto."},
    },
)
def create_item(
    data: Annotated[ItemCreate, Form(media_type="multipart/form-data")],
    session: SessionDep,
    usuario: UsuarioDep,
) -> Item:
    conteudo = preparar_foto(data.foto)
    item = Item.model_validate(data.model_dump(exclude={"foto"}), update={"id_usuario": usuario.id})
    session.add(item)
    session.flush()
    session.add(FotoItem(id_item=item.id, conteudo=conteudo))
    commit_or_conflict(session, "Não foi possível cadastrar o item com a foto.")
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


@router.put(
    "/{id_item}/foto",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Substituir a foto do item",
    responses={
        400: {"description": "Imagem inválida."},
        404: {"description": "Item não encontrado."},
        413: {"description": "Imagem excede o tamanho ou a resolução permitida."},
    },
)
def upload_photo(
    foto: Annotated[UploadFile, File(description="Foto JPEG ou PNG de até 5 MB.")],
    item: ItemDep,
    session: SessionDep,
) -> Response:
    conteudo = preparar_foto(foto)
    registro = session.get(FotoItem, item.id)
    if registro is None:
        registro = FotoItem(id_item=item.id, conteudo=conteudo)
    else:
        registro.conteudo = conteudo
    session.add(registro)
    commit_or_conflict(session, "Não foi possível salvar a foto. Atualize o item e tente novamente.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{id_item}/foto",
    response_class=Response,
    summary="Consultar a foto do item",
    responses={
        200: {"content": {"image/jpeg": {"schema": {"type": "string", "format": "binary"}}}},
        404: {"description": "Item ou foto não encontrado."},
    },
)
def read_photo(item: ItemDep, session: SessionDep) -> Response:
    foto = session.get(FotoItem, item.id)
    if foto is None:
        raise HTTPException(status_code=404, detail="O item não possui foto.")
    return Response(
        content=foto.conteudo,
        media_type="image/jpeg",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )
