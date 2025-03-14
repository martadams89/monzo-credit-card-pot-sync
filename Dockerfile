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

# Copy package files and tailwind config first
COPY package.json package-lock.json* tailwind.config.js ./

# Install npm packages
RUN npm install

# Create directory structure
RUN mkdir -p app/static/css/dist

# Copy CSS source files and templates for Tailwind processing
COPY app/templates ./app/templates
COPY app/static ./app/static

# Build CSS with verification
RUN echo "Building CSS with tailwind..." && \
    npx tailwindcss -i ./app/static/css/src/input.css -o ./app/static/css/dist/output.css --minify && \
    echo "CSS build completed" && \
    ls -la ./app/static/css/dist && \
    echo "CSS file size:" && \
    stat -c %s ./app/static/css/dist/output.css && \
    echo "First few lines:" && \
    head -5 ./app/static/css/dist/output.css

# Back up the built CSS before we copy all other files
RUN cp -a ./app/static/css/dist/output.css /tmp/output.css

# Clean up Node.js dependencies
RUN apt-get purge -y nodejs npm && \
    apt-get autoremove -y && \
    rm -rf node_modules

# Copy Python requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Restore our built CSS file that might have been overwritten
RUN cp -a /tmp/output.css ./app/static/css/dist/output.css && \
    rm /tmp/output.css && \
    echo "Verified CSS exists:" && \
    ls -la ./app/static/css/dist/

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
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "app.wsgi:app"]