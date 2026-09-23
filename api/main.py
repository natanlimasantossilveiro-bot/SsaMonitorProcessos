import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
from fastapi import FastAPI

from api.routers import orgaos, processos

load_dotenv()

app = FastAPI(
    title="SSA Monitor Processos — API de leitura",
    description="API somente leitura sobre o banco do SSA Monitor, consumida pelo Laravel.",
    version="1.0.0",
)

app.include_router(orgaos.router)
app.include_router(processos.router)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("API_HOST", "127.0.0.1")
    port = int(os.getenv("API_PORT", "8001"))

    uvicorn.run(app, host=host, port=port)
