# Base image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Upgrade pip and install dependencies
RUN pip install --upgrade pip setuptools wheel
RUN pip install -r requirements.txt

# Copy all application code
COPY . .

# Expose port (Render sets $PORT automatically)
ENV PORT=10000
EXPOSE $PORT

# Start command (shell form to expand $PORT)
CMD gunicorn --bind 0.0.0.0:$PORT admin_users:app