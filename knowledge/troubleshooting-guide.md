## Problema

Target DOWN en Prometheus

### Posibles causas

- JMeter no está ejecutándose.
- El listener de Prometheus no está configurado.
- El puerto 9270 no está disponible.

### Cómo diagnosticar

```bash
curl http://localhost:9270/metrics
```

### Solución

1. Verificar que JMeter esté ejecutándose.
2. Confirmar que el listener Prometheus esté en el JMX.
3. Revisar la configuración de `prometheus.yml`.
4. Esperar unos segundos para que Prometheus haga el siguiente scrape.