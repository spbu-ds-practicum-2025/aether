FROM python:3.12

WORKDIR /booking

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/booking

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "python create_tables.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
