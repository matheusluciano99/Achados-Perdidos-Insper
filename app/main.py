from contextlib import asynccontextmanager

import fastapi
from sqlmodel import SQLModel

from app.database import engine
from app.routes.items import router as items_router


@asynccontextmanager
async def lifespan(app: fastapi.FastAPI):
    # shortcut: create_all does not migrate existing tables; use migrations for schema changes.
    SQLModel.metadata.create_all(engine)
    yield


app = fastapi.FastAPI(
    title="Achados & Perdidos Insper",
    description="API para cadastro e consulta de objetos encontrados no campus Insper.",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(items_router)


@app.get("/", summary="Consultar mensagem inicial")
async def read_root():
    return {"mensagem": "Achados & Perdidos API"}
