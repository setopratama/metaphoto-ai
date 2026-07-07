FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    libimage-exiftool-perl \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir requests Pillow

WORKDIR /app


COPY main.py .

CMD ["python", "main.py"]
