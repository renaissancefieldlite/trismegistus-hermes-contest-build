FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TRISMEGISTUS_HOST=0.0.0.0 \
    PORT=10000 \
    TRISMEGISTUS_NO_OPEN=1 \
    TRISMEGISTUS_HOSTED_DEMO=1 \
    TRISMEGISTUS_ENABLE_OPENCLAW=0 \
    TRISMEGISTUS_ENABLE_CPU_LLM=0 \
    TRISMEGISTUS_CPU_LLM_CONTEXT=1024 \
    TRISMEGISTUS_CPU_LLM_THREADS=2 \
    TRISMEGISTUS_CPU_LLM_MAX_NEW_TOKENS=140 \
    TRISMEGISTUS_MODEL_TIMEOUT_SECONDS=120 \
    HERMES_TIMEOUT_SECONDS=20

WORKDIR /app

ARG INSTALL_CPU_LLM=0
COPY requirements-cpu.txt .
RUN if [ "$INSTALL_CPU_LLM" = "1" ]; then \
      apt-get update \
      && apt-get install -y --no-install-recommends ca-certificates build-essential cmake \
      && rm -rf /var/lib/apt/lists/* \
      && CMAKE_ARGS="-DLLAMA_NATIVE=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF" \
         CMAKE_BUILD_PARALLEL_LEVEL=1 \
         pip install --no-cache-dir --prefer-binary -r requirements-cpu.txt; \
    fi

COPY . .

EXPOSE 10000

CMD ["python", "-m", "trismegistus.app"]
