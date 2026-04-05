FROM debian:stable-slim

COPY entrypoint.py /entrypoint.py

RUN apt-get update \
    && apt-get install --no-install-recommends -y cloud-init python3 \
    && chmod +x /entrypoint.py \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["/entrypoint.py"]
