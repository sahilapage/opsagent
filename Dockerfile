FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc g++ curl git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Optional deps baked in for full functionality
RUN pip install --no-cache-dir \
    google-auth google-auth-oauthlib google-api-python-client \
    PyGithub python-dateutil playwright beautifulsoup4

RUN python -m playwright install chromium --with-deps

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
