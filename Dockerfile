FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MPLCONFIGDIR=/tmp/matplotlib

WORKDIR /app

RUN groupadd --system portfolio \
    && useradd --system --gid portfolio --create-home portfolio

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY --chown=portfolio:portfolio . ./
RUN mkdir -p /app/instance /tmp/matplotlib \
    && chown -R portfolio:portfolio /app/instance /tmp/matplotlib

USER portfolio

EXPOSE 8000

CMD ["gunicorn", "--workers=2", "--threads=4", "--bind=0.0.0.0:8000", "--timeout=90", "--access-logfile=-", "--error-logfile=-", "app:app"]
