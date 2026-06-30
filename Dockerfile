FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .
COPY glama.json .

ENV TASKSAI_LICENSE_KEY=""
ENV TASKSAI_PRODUCT_ID="farmer"
ENV TASKSAI_API_BASE="https://lawtasksai-api-5gn3dehgyq-uc.a.run.app"

EXPOSE 8080

CMD ["python", "server.py"]
