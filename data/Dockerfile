# Python 3.11, matching requirements.txt
FROM python:3.11-slim

# git is needed to install arinc424 from GitHub (see requirements.txt)
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first so the layer is cached across code changes.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

ENTRYPOINT ["python3", "-u"]
