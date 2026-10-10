import asyncio
import os
from typing import Literal

import psycopg
from fastapi import FastAPI
from pydantic import BaseModel
from redis.asyncio import Redis
from redis.exceptions import RedisError
from starlette.responses import JSONResponse


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["api"] = "api"


app = FastAPI(title="AegisOps foundation", version="0.0.1")


@app.get("/healthz", response_model=Health)
def healthz() -> Health:
    return Health()


async def check_postgres() -> None:
    async with await psycopg.AsyncConnection.connect(
        os.environ["DATABASE_URL"], connect_timeout=3
    ) as connection:
        async with connection.cursor() as cursor:
            await cursor.execute("SELECT 1")
            if await cursor.fetchone() != (1,):
                raise RuntimeError("Database probe failed")


async def check_redis() -> None:
    async with Redis.from_url(
        os.environ["REDIS_URL"], socket_connect_timeout=3, socket_timeout=3
    ) as client:
        if not await client.ping():
            raise RuntimeError("Redis probe failed")


@app.get("/readyz")
async def readyz() -> JSONResponse:
    checks: dict[str, str] = {}
    for name, probe in (("postgres", check_postgres), ("redis", check_redis)):
        try:
            async with asyncio.timeout(3):
                await probe()
            checks[name] = "ok"
        except KeyError, ValueError, TimeoutError, OSError, psycopg.Error, RedisError, RuntimeError:
            checks[name] = "unavailable"
    ready = all(value == "ok" for value in checks.values())
    return JSONResponse(
        {"status": "ready" if ready else "unavailable", "checks": checks},
        status_code=200 if ready else 503,
    )
