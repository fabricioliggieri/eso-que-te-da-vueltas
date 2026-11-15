# El Brujo · «Eso que te da vueltas» · servicio de la pregunta gratis · v0.1 (15/11/2026)
# Python 3.11: pyswisseph 2.10.3.2 publica ruedas hasta 3.11.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    ELBRUJO_EPHE=/app/ephe PREGUNTA_DATOS=/datos TZ=America/Argentina/Buenos_Aires

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Efemérides dentro de la imagen: el servicio no las baja de internet.
COPY ephe/ /app/ephe/
COPY motor/elbrujo_calculo.py /app/motor/
COPY servicio/*.py /app/servicio/
COPY servicio/prompts/ /app/servicio/prompts/

# Usuario sin privilegios; /datos es el volumen de las bases SQLite.
RUN useradd --create-home --uid 10001 brujo && mkdir -p /datos && chown brujo /datos
USER brujo
WORKDIR /app/servicio
EXPOSE 8000
HEALTHCHECK --interval=60s --timeout=10s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/salud',timeout=8)"
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
