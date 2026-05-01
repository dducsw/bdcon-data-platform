FROM python:3.12-slim

WORKDIR /app

# Install dependencies (context is repo root, so path must be full)
COPY datagen/thelook-ecomm/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy datagen code into /app (matches original structure inside container)
COPY datagen/thelook-ecomm/ .

# Copy repo-level src/ so generator.py can import src.clickstream etc.
# This replicates the parents[2] repo-root structure that generator.py expects
COPY src/ ./src/

CMD ["python", "generator.py"]
