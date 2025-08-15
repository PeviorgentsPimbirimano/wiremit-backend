from datetime import datetime, timezone
import asyncio
import httpx
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import delete
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import UserSignup, TokenResponse
from app.auth import hash_password, verify_password, create_access_token
from app.deps import get_current_user
from app.database import engine, Base, get_db, AsyncSessionLocal
from app.models import Rate

# Create FastAPI app first
app = FastAPI(title="Wiremit Forex Service", version="0.1.0")

# In-memory user store
fake_users_db = {}

# ------------------- Startup Events -------------------

@app.on_event("startup")
async def startup():
    # Create DB tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Start background refresh task
    asyncio.create_task(refresh_rates_task())

# ------------------- Health Check ---------------------

@app.get("/health")
def health():
    return {
        "status": "ok",
        "time_utc": datetime.now(timezone.utc).isoformat()
    }

# ------------------- Auth Routes ----------------------

@app.post("/signup", response_model=TokenResponse)
def signup(user: UserSignup):
    if user.email in fake_users_db:
        raise HTTPException(status_code=400, detail="Email already registered")
    fake_users_db[user.email] = {
        "name": user.name,
        "hashed_password": hash_password(user.password)
    }
    token = create_access_token({"sub": user.email})
    return {"access_token": token}

@app.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    db_user = fake_users_db.get(form_data.username)
    if not db_user or not verify_password(form_data.password, db_user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token({"sub": form_data.username})
    return {"access_token": token}

# ------------------- Forex Logic ----------------------

FOREX_APIS = [
    "https://api.exchangerate.host/latest?base=USD",
    "https://open.er-api.com/v6/latest/USD",
    "https://api.frankfurter.app/latest?from=USD"
]

MARKUP_PERCENT = 2.5

async def fetch_aggregated_rates():
    async with httpx.AsyncClient(timeout=5) as client:  # 5s timeout
        tasks = [client.get(url) for url in FOREX_APIS]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

    results = []
    for i, response in enumerate(responses):
        if isinstance(response, Exception):
            print(f"Error fetching from {FOREX_APIS[i]}: {response}")
            continue
        try:
            data = response.json()
            if "rates" in data:
                results.append(data["rates"])
        except Exception as e:
            print(f"Error parsing data from {FOREX_APIS[i]}: {e}")

    if not results:
        raise HTTPException(status_code=500, detail="No API data fetched")

    common_currencies = set(results[0].keys())
    for res in results[1:]:
        common_currencies &= set(res.keys())

    aggregated_rates = {}
    for currency in common_currencies:
        avg_rate = sum(res[currency] for res in results) / len(results)
        marked_up = avg_rate * (1 + MARKUP_PERCENT / 100)
        aggregated_rates[currency] = round(marked_up, 4)

    return aggregated_rates


@app.get("/rates")
async def get_rates(user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    aggregated_rates = await fetch_aggregated_rates()

    await db.execute(delete(Rate))
    for currency, rate in aggregated_rates.items():
        db.add(Rate(
            base="USD",
            currency=currency,
            rate=rate,
            timestamp=datetime.now(timezone.utc)
        ))
    await db.commit()

    return {
        "base": "USD",
        "markup_percent": MARKUP_PERCENT,
        "rates": aggregated_rates
    }

@app.get("/rates/{currency}")
async def get_rate(currency: str, user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Rate).where(Rate.currency == currency.upper())
    )
    rate_obj = result.scalar_one_or_none()
    if not rate_obj:
        raise HTTPException(status_code=404, detail="Currency not found")
    return {
        "base": rate_obj.base,
        "currency": rate_obj.currency,
        "rate": rate_obj.rate,
        "timestamp": rate_obj.timestamp
    }

@app.get("/historical/rates")
async def historical_rates(user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Rate))
    rates_list = result.scalars().all()
    return [
        {
            "base": r.base,
            "currency": r.currency,
            "rate": r.rate,
            "timestamp": r.timestamp
        }
        for r in rates_list
    ]

# ------------------- Background Task ------------------

async def refresh_rates_task():
    while True:
        try:
            async with AsyncSessionLocal() as db:
                rates = await fetch_aggregated_rates()
                await db.execute(delete(Rate))
                for currency, rate in rates.items():
                    db.add(Rate(
                        base="USD",
                        currency=currency,
                        rate=rate,
                        timestamp=datetime.now(timezone.utc)
                    ))
                await db.commit()
        except Exception as e:
            print("Error refreshing rates:", e)
        await asyncio.sleep(3600)
