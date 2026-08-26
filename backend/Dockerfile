FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt requirements-extras.txt requirements-embeddings.txt ./
RUN pip install --no-cache-dir \
    -r requirements.txt \
    -r requirements-extras.txt \
    -r requirements-embeddings.txt

# Pre-download both scene and garment models so removal works without runtime downloads
RUN python -c "from rembg import new_session; new_session('u2net'); new_session('u2net_cloth_seg')"

# Pin and cache the review-only garment embedding model so self-hosted matching
# does not require outbound network access after the image has been built.
ENV HF_HOME=/opt/huggingface
RUN mkdir -p "$HF_HOME"
RUN python -c "from transformers import AutoImageProcessor, AutoModel; revision='ed25f3a31f01632728cabb09d1542f84ab7b0056'; AutoImageProcessor.from_pretrained('facebook/dinov2-small', revision=revision, use_fast=False); AutoModel.from_pretrained('facebook/dinov2-small', revision=revision)"
RUN chmod -R a+rX "$HF_HOME"

# Copy application code
COPY . .

# Create non-root user and storage directory
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
RUN mkdir -p /data/wardrobe /data/uploads && chown -R appuser:appuser /data

# Entrypoint drops to appuser (remapped to PUID/PGID when set); when the
# container is started as a non-root uid (e.g. k8s runAsUser) it execs directly
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN sed -i 's/\r$//' /docker-entrypoint.sh && chmod +x /docker-entrypoint.sh
ENTRYPOINT ["/docker-entrypoint.sh"]

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
