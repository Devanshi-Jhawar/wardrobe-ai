FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# EMBEDDING_BACKEND=clip installs CPU-only PyTorch + open_clip (much larger image).
ARG EMBEDDING_BACKEND=color
COPY requirements.txt requirements-clip.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
 && if [ "$EMBEDDING_BACKEND" = "clip" ]; then \
      pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
      && pip install --no-cache-dir -r requirements-clip.txt; \
    fi
COPY app ./app
ENV EMBEDDING_BACKEND=${EMBEDDING_BACKEND}
EXPOSE 8003
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
