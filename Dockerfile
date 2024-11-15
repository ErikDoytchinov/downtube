# Dockerfile

# Use the official Python 3.11 image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV POETRY_VERSION=1.5.1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential

# Install Poetry
RUN pip install "poetry==$POETRY_VERSION"

# Copy only the dependency files to leverage Docker cache
COPY pyproject.toml poetry.lock /app/

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

# Copy the rest of the application code
COPY . /app

# Expose the port FastAPI will run on
EXPOSE 8000

# Command to run the application
CMD ["poetry", "run", "uvicorn", "downtube:app", "--host", "0.0.0.0", "--port", "8000"]