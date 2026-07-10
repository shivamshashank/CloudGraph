FROM python:3.11-alpine
WORKDIR /app
RUN pip install --no-cache-dir requests neo4j
COPY main.py /usr/local/bin/investigation-engine
CMD ["python", "/usr/local/bin/investigation-engine"]
