FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml README.md ./
COPY app ./app
COPY training ./training

RUN addgroup --system evalforge && adduser --system --ingroup evalforge evalforge
RUN pip install --upgrade pip && pip install --no-cache-dir -e .
RUN chown -R evalforge:evalforge /app

EXPOSE 8000

USER evalforge

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
