FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    libimage-exiftool-perl \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY main.py .

CMD ["python", "main.py"]
