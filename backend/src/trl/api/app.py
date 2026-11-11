from fastapi import FastAPI
from pydantic import BaseModel


class Health(BaseModel):
    status: str = "ok"


app = FastAPI(title="Transit Replan Lab", version="0.1.0")


@app.get("/healthz")
async def health() -> Health:
    return Health()
