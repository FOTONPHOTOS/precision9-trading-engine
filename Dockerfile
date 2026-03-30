# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed system dependencies (e.g., for building certain Python packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# Using --no-cache-dir reduces the image size
RUN pip install --no-cache-dir -r requirements.txt

# Install technical analysis library - handling different possible names
RUN pip install --no-cache-dir --upgrade pandas-ta || pip install --no-cache-dir --upgrade pandas_ta || echo "Warning: Could not install technical analysis library (pandas-ta or pandas_ta), some functionality may be limited"

# Copy the rest of your application's code from the host's 'app' directory to the container's '/app' directory
COPY ./app .
COPY ./config_tuning /app/config_tuning

# Install additional dependencies for eyes_of_horus if they exist
RUN if [ -f /app/eyes_of_horus/requirements.txt ]; then pip install --no-cache-dir -r /app/eyes_of_horus/requirements.txt; fi

# Create necessary directories
RUN mkdir -p /app/logs && mkdir -p /app/eyes_of_horus/logs

# This Dockerfile doesn't specify a CMD or ENTRYPOINT because
# docker-compose will be responsible for running the different services.

