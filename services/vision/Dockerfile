FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# OpenCV (pulled in by ultralytics) needs these system libraries.
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
# CPU-only PyTorch first, so ultralytics doesn't pull the multi-GB CUDA build.
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements.txt
COPY main.py .
# The trained model is mounted here by docker-compose.yml (runs/detect/train-2/weights).
ENV MODEL_PATH=/models/best.pt YOLO_CONFIG_DIR=/tmp/ultralytics
EXPOSE 8002
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
