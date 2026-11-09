FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy files preserving both package and top-level paths
COPY backend/ ./backend/
COPY backend/ ./
COPY app/ ./app/
COPY logs/ ./logs/

EXPOSE 5000

CMD ["python", "server.py"]
