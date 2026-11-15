# Eso que te da vueltas · código fuente

Código del servicio que responde «Eso que te da vueltas», la pregunta gratis de [elbrujolecturas.com](https://elbrujolecturas.com).

- `motor/`: el cálculo (astrología con Swiss Ephemeris, numerología y Bazi).
- `servicio/`: el servicio web (FastAPI): filtros, límites, cálculo de la pregunta, llamadas al modelo y controles.
- `servicio/prompts/`: las instrucciones que usa el modelo.

## Licencia

GNU Affero General Public License v3.0 (ver `LICENSE`). El servicio usa Swiss Ephemeris (Astrodienst AG) a través de pyswisseph, bajo la AGPL; por eso este código se publica con la misma licencia.

Las efemérides (`sepl_18.se1`, `semo_18.se1`, `seas_18.se1`) no están en esta copia: se bajan de Astrodienst (https://github.com/aloistr/swisseph/tree/master/ephe) y van en la carpeta `ephe/`.

## Cómo se corre

Con las tres efemérides en `ephe/`:

```
docker build -t pregunta .
docker run --env-file .env -v pregunta_datos:/datos pregunta
```

Variables: `ANTHROPIC_API_KEY`, `PREGUNTA_ABIERTA` (`si` / `no`), `PREGUNTA_TOPE_DIA`, `PREGUNTA_TOPE_HORA`, `TURNSTILE_SECRET` y, opcionales, `PREGUNTA_TOKEN` y `PREGUNTA_SAL` (si falta, se crea sola en `/datos`).
