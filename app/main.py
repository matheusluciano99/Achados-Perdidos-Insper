from contextlib import asynccontextmanager

import fastapi
from sqlmodel import SQLModel

from app.auth import exigir_autenticacao
from app.database import engine
from app.routes.auth import router as auth_router
from app.routes.items import router as items_router
from app.routes.retiradas import router as retiradas_router


@asynccontextmanager
async def lifespan(app: fastapi.FastAPI):
    # shortcut: create_all does not migrate existing tables; use migrations for schema changes.
    SQLModel.metadata.create_all(engine)
    yield


app = fastapi.FastAPI(
    title="Achados & Perdidos Insper",
    description="API para cadastro de objetos encontrados no campus Insper e registro de suas retiradas.",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(auth_router)
app.include_router(items_router, dependencies=[fastapi.Depends(exigir_autenticacao)])
app.include_router(retiradas_router, dependencies=[fastapi.Depends(exigir_autenticacao)])


@app.get("/", summary="Consultar mensagem inicial")
async def read_root():
    return {"mensagem": "Achados & Perdidos API"}
