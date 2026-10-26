FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Create + seed the SQLite database (orders.db)
RUN python database/init_db.py

EXPOSE 5004

# One Flask app: cart page + REST CRUD API + AI helper (port 5004)
CMD ["python", "backend/main.py"]
