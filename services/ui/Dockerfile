FROM python:3.11-alpine
WORKDIR /app
COPY mock_service.py /app/mock_service.py
COPY static /app/static
ENV PORT=3000
CMD ["python", "/app/mock_service.py"]
