#!/bin/bash

# Create required directories
mkdir -p app/static/css/dist
mkdir -p app/static/css/src

# Ensure input.css exists
if [ ! -f app/static/css/src/input.css ]; then
  echo "@tailwind base;
@tailwind components;
@tailwind utilities;" > app/static/css/src/input.css
  echo "Created input.css"
fi

# Try to build CSS with npm
if command -v npm &> /dev/null; then
  echo "Building CSS with npm..."
  npm run build-css
elif command -v npx &> /dev/null; then
  echo "Building CSS with npx directly..."
  npx tailwindcss -i ./app/static/css/src/input.css -o ./app/static/css/dist/output.css
else
  echo "Creating basic CSS file as fallback..."
  cat > app/static/css/dist/output.css << EOL
/* Basic fallback styles */
:root { --main-bg-color: #ffffff; --main-text-color: #1f2937; }
@media (prefers-color-scheme: dark) {
    :root { --main-bg-color: #1f2937; --main-text-color: #f3f4f6; }
}
body { 
    font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    background-color: var(--main-bg-color);
    color: var(--main-text-color);
    line-height: 1.5;
}
.container { width: 100%; max-width: 1280px; margin: 0 auto; padding: 0 1rem; }
.bg-white { background-color: #ffffff; }
.dark .bg-white { background-color: #374151; }
EOL
fi

echo "CSS setup complete"
