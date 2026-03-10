ARG BUILD_FROM
FROM $BUILD_FROM

WORKDIR /app

RUN apk add --no-cache python3 py3-pip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python3", "/app/main.py"]
