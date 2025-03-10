FROM python:3.9-slim

WORKDIR /app

# Install system dependencies including Node.js
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    build-essential \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Copy package files for CSS building
COPY package.json package-lock.json* ./

# Install npm packages
RUN npm install

# Copy CSS source files
COPY app/static/css/src ./app/static/css/src
COPY tailwind.config.js ./

# Build CSS
RUN mkdir -p app/static/css/dist && \
    npx tailwindcss -i ./app/static/css/src/input.css -o ./app/static/css/dist/output.css --minify

# Clean up npm packages after CSS is built
RUN apt-get purge -y nodejs npm && \
    apt-get autoremove -y && \
    rm -rf node_modules

# Copy Python requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code (after CSS is built)
COPY . .

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=app.wsgi:app

# Create volume for SQLite database
VOLUME /app/instance

# Expose port
EXPOSE 8000

# Run the entry point script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh
ENTRYPOINT ["/docker-entrypoint.sh"]

# Default command
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "app.wsgi:app"]