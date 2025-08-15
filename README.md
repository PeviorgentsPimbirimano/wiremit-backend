# Wiremit Forex Backend – FastAPI

A backend service built with **FastAPI** that:
- Fetches forex rates from multiple public APIs
- Calculates an average rate and applies a markup for customer-facing rates
- Stores rates in a database (SQLite)
- Requires JWT authentication for protected endpoints

---

##  Tech Stack
- **FastAPI** – Web framework
- **SQLite** – Local database
- **SQLAlchemy** – ORM
- **httpx** – Async HTTP client
- **JWT (python-jose)** – Token-based authentication
- **passlib** – Password hashing

---

##  How to Run the API

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd wiremit-forex
Create and activate a virtual environment
Windows PowerShell:

powershell

python -m venv .venv
.\.venv\Scripts\Activate.ps1
macOS/Linux:

bash

python -m venv .venv
source .venv/bin/activate
Install dependencies

bash

pip install uvicorn[standard] fastapi sqlalchemy aiosqlite httpx python-jose[cryptography] passlib[bcrypt] pydantic[email]
Run the API

bash

python -m uvicorn app.main:app --reload
Access Swagger Docs

arduino

http://127.0.0.1:8000/docs
 Authentication Flow
Sign up

POST /signup → Accepts JSON:

json

{
  "email": "user@example.com",
  "name": "John Doe",
  "password": "yourpassword"
}
Stores the user in memory (demo only) with a hashed password.

Returns a JWT access token.

Login

POST /login → Accepts form data (OAuth2PasswordRequestForm):

username = email

password = your password

Returns a JWT access token.

Authorize in Swagger

Click Authorize

Enter email & password

Swagger stores the Bearer token for future requests

Protected Endpoints
The following require the JWT in the Authorization: Bearer <token> header:

GET /rates

GET /rates/{currency}

GET /historical/rates

 Rate Aggregation Logic
Fetch rates from three public APIs in parallel:

https://api.exchangerate.host/latest?base=USD

https://open.er-api.com/v6/latest/USD

https://api.frankfurter.app/latest?from=USD

Normalize responses to extract the rates dictionary.

Find common currencies available in all API responses.

Average rates for each currency.

Apply markup
Example with 2.5% markup:

python

marked_up = avg_rate * (1 + 2.5 / 100)
Save to DB

Deletes old rates (delete(Rate))

Inserts the latest rates with a timestamp

Return JSON

json

{
  "base": "USD",
  "markup_percent": 2.5,
  "rates": {
    "EUR": 0.919,
    "GBP": 0.792,
    "ZAR": 18.735
  }
}
 Endpoints Overview
Method	 Endpoint	    Auth Required	    Description
GET	    /health	            No	           Health check
POST	/signup	            No	           Create a new user
POST	/login	            No	           Login and receive JWT token
GET	    /rates	            Yes	           Fetch, average, markup, save & return rates
GET	    /rates/{currency}   Yes	           Return rate for specific currency
GET	    /historical/rates   Yes	           Return latest stored rates

## 🖼 Architecture Overview


    ┌───────────────┐
    │  Public APIs  │
    │ (3 Providers) │
    └───────┬───────┘
            │  Fetch (httpx, async)
            ▼
   ┌───────────────────┐
   │ Aggregation Logic │
   │ - Normalize rates │
   │ - Find intersection│
   │ - Average rates   │
   │ - Apply markup    │
   └─────────┬─────────┘
             │  Save to DB (SQLAlchemy + SQLite)
             ▼
    ┌─────────────────────┐
    │     Database        │
    │     (forex.db)      │
    └─────────┬───────────┘
              │
   ┌──────────▼──────────┐
   │   FastAPI App       │
   │  Auth (JWT) + Routes│
   └──────────┬──────────┘
              │
    ┌─────────▼─────────┐
    │   Client (Swagger │
    │  / Postman / App) │
    └───────────────────┘


    This shows:
- **Top**: External public forex APIs feeding your system
- **Middle**: Your aggregation logic & DB
- **Bottom**: FastAPI endpoints accessed via an authenticated client  
