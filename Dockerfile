FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml requirements.txt requirements-lock.txt ./
COPY src ./src
COPY web ./web
COPY sniplink.toml README.md LICENSE ./

RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt -c requirements-lock.txt \
    && python -m pip install -e . -c requirements-lock.txt

EXPOSE 8000

CMD ["sh", "-c", "python web/manage.py migrate && exec python web/manage.py runserver 0.0.0.0:8000"]
