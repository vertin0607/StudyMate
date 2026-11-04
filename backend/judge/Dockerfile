FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends g++ python3 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 --shell /usr/sbin/nologin judge \
    && mkdir -p /opt/judge \
    && chown root:root /opt/judge

COPY runner.py /opt/judge/runner.py

USER judge
WORKDIR /tmp
ENV PYTHONDONTWRITEBYTECODE=1
ENV HOME=/tmp

ENTRYPOINT ["python3", "/opt/judge/runner.py"]
