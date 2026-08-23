# JMeter Best Practices

## Objetivo

Este documento define las prácticas recomendadas para diseñar, ejecutar y mantener pruebas de rendimiento con Apache JMeter dentro de la plataforma AI Performance Engineering.

## Principios generales

Toda prueba JMeter debe ser:

- repetible;
- parametrizable;
- observable;
- segura;
- trazable;
- ejecutable en modo no-GUI;
- capaz de generar evidencia completa.

## Ejecución no-GUI

Las pruebas deben ejecutarse con:

```bash
jmeter -n \
  -t test_plan.jmx \
  -l results.jtl \
  -j jmeter.log