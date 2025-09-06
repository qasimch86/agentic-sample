# Python 3.13 base image
FROM python:3.13

# Set working directory
WORKDIR /app

# Copy all project files
COPY . /app

# Create virtual environment
RUN python -m venv /app/.venv

# Activate venv and install requirements
RUN /bin/bash -c "source /app/.venv/bin/activate && pip install --upgrade pip && pip install -r requirements-minimal.txt"

# Expose port
EXPOSE 8001

# Default command
CMD ["/app/.venv/bin/python", "app.py"]
