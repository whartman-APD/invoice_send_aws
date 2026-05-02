# Use Python 3.11 slim image (matches Lambda runtime)
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install ODBC Driver 18 for SQL Server (required by pyodbc for Azure SQL)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl gnupg2 unixodbc-dev \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 libgssapi-krb5-2 \
    && apt-get purge -y --auto-remove curl gnupg2 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY shared/ ./shared/
COPY assets/ ./assets/
COPY entrypoint.py .

# Set PYTHONPATH to include shared modules
ENV PYTHONPATH="/app/shared:${PYTHONPATH}"

# Set the entrypoint
ENTRYPOINT ["python", "entrypoint.py"]
