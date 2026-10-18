FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Fijamos /app como directorio de trabajo para mantener coherencia
WORKDIR /app

# Copiamos e instalamos dependencias en /app/
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el resto del código del servicio
COPY . .

EXPOSE 5000

CMD ["python", "api.py"]