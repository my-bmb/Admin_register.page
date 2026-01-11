# Base image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install dependencies
RUN pip install --upgrade pip setuptools wheel
RUN pip install -r requirements.txt

# Copy app code
COPY . .

# Expose port (Render uses $PORT)
ENV PORT=10000
EXPOSE $PORT

# Start command
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "admin_users:app"]