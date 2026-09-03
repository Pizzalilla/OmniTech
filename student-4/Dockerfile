FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY backend/requirements.txt ./backend_reqs.txt
COPY database/requirements.txt ./db_reqs.txt
RUN pip install --no-cache-dir -r backend_reqs.txt -r db_reqs.txt

# Copy source code
COPY . .

# Initialize SQLite seed data
RUN python database/init_db.py

EXPOSE 5004 5014

# Startup script to run both Database (5004) and Backend (5014) concurrently
CMD python database/app.py & python backend/app.py
