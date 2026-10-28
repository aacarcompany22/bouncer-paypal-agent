
#!/bin/bash
export PORT="${PORT:-10000}"

uvicorn webhook_server:app --host 127.0.0.1 --port 8000 &
streamlit run app.py \
  --server.port 8501 --server.address 127.0.0.1 --server.headless true \
  --server.enableCORS false --server.enableXsrfProtection false \
  --browser.gatherUsageStats false &
caddy run --config /app/Caddyfile --adapter caddyfile &

# if any of the three stops, exit so Render restarts the whole container
wait -n
exit 1