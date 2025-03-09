"""Utility to ensure CSS files exist and are accessible."""

import os
import logging
import subprocess
from pathlib import Path

log = logging.getLogger("css_generator")

def ensure_css_directories():
    """Ensure that all required CSS directories exist."""
    # Get app root directory
    app_dir = Path(__file__).parent.parent
    
    # Ensure directories exist
    css_dir = app_dir / 'static' / 'css'
    dist_dir = css_dir / 'dist'
    src_dir = css_dir / 'src'
    
    os.makedirs(dist_dir, exist_ok=True)
    os.makedirs(src_dir, exist_ok=True)
    
    return dist_dir, src_dir

def generate_minimal_css():
    """Generate a minimal CSS file if output.css doesn't exist."""
    dist_dir, src_dir = ensure_css_directories()
    
    # Check if output CSS exists
    output_css = dist_dir / 'output.css'
    input_css = src_dir / 'input.css'
    
    # Create input.css if it doesn't exist
    if not input_css.exists():
        log.info(f"Creating minimal input.css at {input_css}")
        with open(input_css, 'w') as f:
            f.write("@tailwind base;\n@tailwind components;\n@tailwind utilities;\n")
    
    # Create output.css if it doesn't exist or is empty
    if not output_css.exists() or os.path.getsize(output_css) == 0:
        log.info(f"Output CSS not found. Creating minimal output.css at {output_css}")
        try:
            # Try to run the build command if possible
            project_root = Path(__file__).parent.parent.parent
            tailwind_config = project_root / 'tailwind.config.js'
            
            if tailwind_config.exists() and os.path.exists('/usr/local/bin/npx') or os.path.exists('/usr/bin/npx'):
                try:
                    log.info("Attempting to build CSS with Tailwind...")
                    subprocess.run(
                        ["npx", "tailwindcss", "-i", str(input_css), "-o", str(output_css)],
                        check=True,
                        timeout=10
                    )
                    log.info("Tailwind CSS build successful!")
                    return True
                except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
                    log.warning(f"Failed to build with Tailwind: {e}")
            
            # Fallback to a basic CSS if build fails
            log.info("Creating minimal CSS file as fallback")
            with open(output_css, 'w') as f:
                f.write("""
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
                """)
                return True
        except Exception as e:
            log.error(f"Failed to create CSS file: {e}")
            return False
    
    return True

if __name__ == "__main__":
    # When run directly, ensure CSS exists
    logging.basicConfig(level=logging.INFO)
    generate_minimal_css()
