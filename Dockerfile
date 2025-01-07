FROM python:3.12-alpine
WORKDIR /app

# Install poetry
RUN pip install poetry==2.0.0

# Copy only dependency files initially
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction --no-ansi --no-root

# Copy the rest of the application
COPY . .

# Run the application
ENTRYPOINT ["/app/entrypoint.sh"]
