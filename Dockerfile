FROM python:3.12

# work dir
WORKDIR /app

COPY requirements.txt .

# install packages without cache
RUN pip install --no-cache-dir -r requirements.txt

# copy project
COPY . .

EXPOSE 8000

CMD ["python", "app/manage.py", "runserver", "0.0.0.0:8000"]