# ---------- Frontend build (Node) ----------
FROM node:18-slim AS frontend
WORKDIR /frontend

# Install dependencies separately for better caching
COPY apps/legal_discovery/package*.json ./
RUN npm ci

# Build the React bundle so Flask can serve precompiled assets
COPY apps/legal_discovery/ ./
RUN npm run build


# ---------- Backend (Python) ----------
# Coqui TTS does not yet provide wheels for Python 3.12, which caused
# `pip install` to fail during the image build.  Use Python 3.11 until
# upstream support is available.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=0

WORKDIR /usr/src/app

# System deps:
# - build-essential + pkg-config for building wheels
# - WeasyPrint runtime libs (cairo/pango/gdk-pixbuf/fontconfig)
# - tesseract-ocr (since pytesseract is in requirements)
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential pkg-config \
      libcairo2 libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 \
      libgdk-pixbuf-2.0-0 libffi8 libffi-dev \
      libxml2 libxslt1.1 fonts-liberation \
      tesseract-ocr tesseract-ocr-eng \
      ffmpeg libsndfile1 espeak \
      curl \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip/setuptools for installation
RUN python -m pip install --upgrade pip setuptools wheel

# Install Python deps early to leverage Docker layer cache
COPY apps/legal_discovery/requirements.txt ./requirements.txt

# Install dependencies and pull the CPU-only torch wheel directly
RUN pip install https://download.pytorch.org/whl/cpu/torch-2.5.1%2Bcpu-cp311-cp311-linux_x86_64.whl \
    && pip install -r requirements.txt

# Optional: If you rely on spaCy model via `spacy download`, you can skip this
# because your requirements already install the model wheel from GitHub.
# Keeping it is harmless, but adds time:
# RUN python -m spacy download en_core_web_sm

COPY . .

# Bring in built static assets from the frontend stage
COPY --from=frontend /frontend/static apps/legal_discovery/static

# Clean up any leftover frontend dev folders (defensive)
RUN rm -rf apps/legal_discovery/node_modules

# Expose app port
EXPOSE 5001

HEALTHCHECK --interval=30s --retries=5 CMD curl -fsS http://localhost:5001/api/health || exit 1

# Environment defaults (can be overridden at runtime)
ENV AGENT_MANIFEST_FILE=/usr/src/app/registries/manifest.hocon \
    AGENT_LLM_INFO_FILE=/usr/src/app/registries/llm_config.hocon
ENV FLASK_SECRET_KEY=[] \
    JWT_SECRET=[]

# Run the Flask app via gunicorn+eventlet. Graph schema is bootstrapped in
# Run the Flask app via gunicorn+eventlet
CMD ["gunicorn", "-k", "eventlet", "-w", "1", "-b", "0.0.0.0:5001", "apps.legal_discovery.startup:app"]
