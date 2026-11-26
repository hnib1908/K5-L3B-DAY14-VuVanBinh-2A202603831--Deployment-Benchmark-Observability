"""
Production AI Agent - Part 6 Final Project
"""
import json
import logging
import sys
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone

import redis
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.config import settings
from utils.mock_llm import ask as llm_ask


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "lvl": record.levelname,
            "event": record.getMessage(),
            "logger": record.name,
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _setup_logging():
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    for name in ("", "uvicorn", "uvicorn.error", "uvicorn.access", __name__):
        lg = logging.getLogger(name)
        lg.handlers = [handler]
        lg.setLevel(logging.INFO)
        lg.propagate = False


_setup_logging()
logger = logging.getLogger(__name__)

_redis = None
_mem_rate = {}
_mem_spent = {"date": "", "amount": 0.0}
COST_PER_REQUEST_USD = 0.01


def get_redis():
    global _redis
    if _redis is None:
        _redis = redis.from_url(
            settings.redis_url,
            socket_connect_timeout=1,
            socket_timeout=1,
            decode_responses=True,
        )
    return _redis


def redis_ping():
    try:
        return bool(get_redis().ping())
    except Exception:
        return False


def check_rate_limit(client_id: str):
    limit = settings.rate_limit_per_minute
    window = int(time.time() // 60)
    key = f"ratelimit:{client_id}:{window}"
    try:
        count = get_redis().incr(key)
        if count == 1:
            get_redis().expire(key, 60)
    except Exception:
        mk = (client_id, window)
        count = _mem_rate.get(mk, 0) + 1
        _mem_rate[mk] = count
    if count > limit:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


def _spent_today():
    today = date.today().isoformat()
    try:
        return float(get_redis().get(f"budget:{today}") or 0.0)
    except Exception:
        return _mem_spent["amount"] if _mem_spent["date"] == today else 0.0


def check_budget():
    if _spent_today() >= settings.daily_budget_usd:
        raise HTTPException(status_code=402, detail="Daily budget exceeded")


def record_cost():
    today = date.today().isoformat()
    try:
        get_redis().incrbyfloat(f"budget:{today}", COST_PER_REQUEST_USD)
        get_redis().expire(f"budget:{today}", 86400)
    except Exception:
        if _mem_spent["date"] != today:
            _mem_spent["date"] = today
            _mem_spent["amount"] = 0.0
        _mem_spent["amount"] += COST_PER_REQUEST_USD


def verify_api_key(x_api_key: str = Header(default=None, alias="X-API-Key")):
    if settings.agent_api_key and x_api_key != settings.agent_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return x_api_key


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup")
    yield
    # Graceful shutdown: SIGTERM -> finish in-flight requests, then close Redis
    logger.info("graceful shutdown: SIGTERM handling, closing connections")
    try:
        if _redis is not None:
            _redis.close()
    except Exception:
        pass


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    if redis_ping():
        return {"ready": True}
    return JSONResponse(status_code=503, content={"ready": False})


@app.post("/ask")
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    check_rate_limit(api_key or "anonymous")
    check_budget()
    start = time.time()
    answer = llm_ask(body.question)
    record_cost()
    logger.info(f"request path=/ask status=200 ms={round((time.time() - start) * 1000, 1)}")
    return {"question": body.question, "answer": answer}
