FROM python:3.12-alpine
WORKDIR /app

# Install poetry
RUN pip install poetry

# Copy only dependency files initially
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction --no-ansi

# Copy the rest of the application
COPY . .

EXPOSE 8000

# Run the application
ENTRYPOINT ["poetry", "run", "python", "src/main.py"]