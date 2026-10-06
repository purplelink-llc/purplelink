FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg tini && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY chiptune.py voices.py scene.py stream.py broadcast.py ./
ENV PYTHONUNBUFFERED=1
# STREAM_URL (the full rtmp URL with the key) comes from the environment, never from the image.
ENTRYPOINT ["tini", "--"]
CMD ["python", "stream.py", "--live"]
