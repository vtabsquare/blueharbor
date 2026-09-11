#!/bin/bash

# Enforce backend port
export BLUEHARBOR_API_PORT=8001

# Start Python backend
python backend/server.py &

# Start Vinext production server
npx vinext start -H 127.0.0.1 -p 3000 &

# Start Caddy
caddy run --config /app/Caddyfile &

# Wait for any background process to exit
wait -n

# Exit with the status of the process that failed
exit $?
