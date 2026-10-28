
FROM python:3.14-slim

# Caddy: one public port that routes /webhook to FastAPI and everything else to Streamlit
COPY --from=caddy:2 /usr/bin/caddy /usr/local/bin/caddy

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN sed -i 's/\r$//' start.sh Caddyfile
ENV PYTHONUNBUFFERED=1
CMD ["bash", "start.sh"]