FROM python:3.11-slim

WORKDIR /app

# System deps for Playwright are installed via playwright itself.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
    && python -m playwright install --with-deps chromium

# App code
COPY . /app/web_agent

# Run module by default (args can be appended)
ENTRYPOINT ["python", "-m", "web_agent"]
