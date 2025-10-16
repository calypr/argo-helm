FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py /app/
ENV FENCE_BASE="https://calypr-dev.ohsu.edu/user" HTTP_TIMEOUT=3.0
EXPOSE 8080
CMD ["gunicorn", "-b", "0.0.0.0:8080", "--access-logfile", "-", "app:app"]
