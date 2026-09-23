FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Do not copy .env secrets to production images
RUN rm -f .env

EXPOSE 8001
CMD ["python", "server.py", "8001"]
