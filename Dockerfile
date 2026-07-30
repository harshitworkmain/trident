# Use official lightweight Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /code

# Copy and install python requirements
COPY requirements-prod.txt /code/requirements-prod.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements-prod.txt

# Copy all application files
COPY . .

# Grant write permissions to the workspace directory so SQLite can create/write files
RUN chmod -R 777 /code

# Expose port 7860 (Hugging Face default)
EXPOSE 7860

# Run Flask application using Gunicorn (binding to $PORT with a fallback to 7860)
CMD ["sh", "-c", "gunicorn -b 0.0.0.0:${PORT:-7860} app:app"]
