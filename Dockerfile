FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install Node.js + MCP weather server (глобально, без npx)
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs npm \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g @dangahagan/weather-mcp@latest

WORKDIR /app

COPY requirements.txt .
RUN uv pip install --system --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

CMD ["python", "run.py"]