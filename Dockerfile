FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y gcc portaudio19-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY denwa_app.py .

EXPOSE 8080

CMD ["streamlit", "run", "denwa_app.py", "--server.port=8080", "--server.address=0.0.0.0"]
