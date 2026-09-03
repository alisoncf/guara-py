FROM python:3.11-slim

WORKDIR /app

COPY . /app

# Instala dependências do sistema (opcional: poppler para PDF to PNG)
RUN apt update && apt install -y poppler-utils && \
    pip install --upgrade pip && \
    pip install torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install -r requirements.txt

EXPOSE 5000

CMD ["python", "-m", "app.main"]
