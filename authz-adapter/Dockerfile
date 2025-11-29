FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py /app/
COPY templates/ /app/templates/
# Create default content directory
RUN mkdir -p /content
ENV FENCE_BASE="https://calypr-dev.ohsu.edu/user" HTTP_TIMEOUT=3.0 CONTENT_DIR="/content"
EXPOSE 8080
CMD ["gunicorn", "-b", "0.0.0.0:8080", "--access-logfile", "-", "app:app"]
