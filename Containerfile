FROM python:3.11-slim

RUN pip install --no-cache-dir lxml>=4.9

WORKDIR /app
COPY emx/ ./emx/
COPY main.py rewire.py ./

RUN ln -s /app/main.py /usr/local/bin/emx-validate && \
    ln -s /app/rewire.py /usr/local/bin/emx-rewire && \
    chmod +x /app/main.py /app/rewire.py

ENV PYTHONPATH=/app

WORKDIR /workspace

ENTRYPOINT []
CMD ["python", "/app/main.py", "--help"]
