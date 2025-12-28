# Use Python 3.11 slim image (matches Lambda runtime)
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY shared/ ./shared/
COPY send_invoices/ ./send_invoices/
COPY create_invoices/ ./create_invoices/
COPY assets/ ./assets/
COPY entrypoint.py .

# Set PYTHONPATH to include shared modules
ENV PYTHONPATH="/app/shared:${PYTHONPATH}"

# Set the entrypoint
ENTRYPOINT ["python", "entrypoint.py"]
