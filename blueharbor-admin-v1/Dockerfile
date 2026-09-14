FROM python:3.12-slim

# Install Node.js 22, Caddy, and dependencies
RUN apt-get update && \
    apt-get install -y curl debian-keyring debian-archive-keyring apt-transport-https && \
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg && \
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get update && \
    apt-get install -y nodejs caddy && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Node dependencies
COPY package.json package-lock.json ./
RUN npm ci

# Install Python dependencies
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy application source code
COPY . .

# Build frontend
ARG BLUEHARBOR_BUYER_URL
ENV NEXT_PUBLIC_BUYER_URL=$BLUEHARBOR_BUYER_URL
RUN npm run build

# Ensure startup script is executable
RUN chmod +x /app/start.sh

# Render uses the PORT environment variable
ENV PORT=8080

CMD ["/app/start.sh"]
