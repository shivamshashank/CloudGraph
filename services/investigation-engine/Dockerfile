FROM python:3.11-alpine
WORKDIR /app
RUN pip install --no-cache-dir requests neo4j
COPY main.py /usr/local/bin/investigation-engine
# -u forces unbuffered stdout. Without it Python block-buffers when
# stdout is a pipe, so [LLM REQUEST]/[LLM RESPONSE] lines flushed
# minutes late and landed in a LATER scenario's `kubectl logs
# --since-time window -- rcaeval-03 captured rcaeval-02 prompts.
ENV PYTHONUNBUFFERED=1
CMD ["python", "-u", "/usr/local/bin/investigation-engine"]
