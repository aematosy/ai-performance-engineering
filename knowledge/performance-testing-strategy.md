# Performance Testing Strategy

## Objetivo

Este documento define la estrategia utilizada por la plataforma AI Performance Engineering para diseñar y ejecutar pruebas de rendimiento de manera segura, repetible y basada en evidencia.

El objetivo principal es responder una pregunta concreta del negocio o de la arquitectura, evitando ejecutar pruebas sin propósito.

---

# Principios

Toda prueba debe cumplir los siguientes principios:

- Tener un objetivo definido.
- Tener autorización para ejecutarse.
- Ser repetible.
- Generar evidencia.
- Ser medible.
- Tener criterios claros de éxito o fracaso.

Nunca ejecutar una prueba únicamente para "ver qué pasa".

---

# Flujo recomendado

```text
Requerimiento
        │
        ▼
Diseño del escenario
        │
        ▼
Validación del ambiente
        │
        ▼
Generación del JMX
        │
        ▼
Validación técnica
        │
        ▼
Ejecución
        │
        ▼
Análisis SLA
        │
        ▼
Reporte Ejecutivo
        │
        ▼
Recomendaciones
```

---

# Tipos de prueba

## Baseline

### Objetivo

Obtener una referencia inicial del comportamiento del sistema.

### Cuándo utilizarlo

- Primera ejecución.
- Validación del pipeline.
- Validación del ambiente.
- Validación de observabilidad.
- Verificación de latencia inicial.

### Configuración sugerida

- 1–10 usuarios
- Ramp-up gradual
- 15–60 segundos

### Limitaciones

No demuestra capacidad máxima.

No demuestra escalabilidad.

---

## Load Test

### Objetivo

Validar la carga esperada del negocio.

### Cuándo utilizarlo

- Existe una concurrencia conocida.
- Existe un SLA definido.
- Existe monitoreo de infraestructura.

### Configuración

Depende del negocio.

Debe representar usuarios reales.

---

## Stress Test

### Objetivo

Encontrar el límite del sistema.

### Reglas

Incrementar carga por etapas.

Nunca comenzar directamente con la carga máxima.

Registrar el punto de degradación.

---

## Spike Test

### Objetivo

Validar la reacción del sistema frente a incrementos bruscos de tráfico.

Debe observarse:

- recuperación
- errores
- tiempos
- estabilidad

---

## Endurance Test

### Objetivo

Detectar degradación acumulativa.

Buscar:

- Memory leaks
- Saturación
- GC
- Pools
- Caché

---

# Estrategia incremental

Siempre aumentar la carga gradualmente.

Ejemplo:

Baseline

↓

10 usuarios

↓

25 usuarios

↓

50 usuarios

↓

100 usuarios

↓

Stress

Nunca saltar directamente de 5 usuarios a 500.

---

# Autorización

Antes de ejecutar debe existir confirmación explícita del usuario.

No ejecutar producción sin autorización.

---

# Información mínima requerida

Antes de ejecutar una prueba se debe conocer:

- escenario
- ambiente
- target
- método HTTP
- usuarios
- ramp-up
- duración
- SLA
- autorización

---

# Evidencias mínimas

Cada ejecución debe generar:

- JMX
- JTL
- Log de JMeter
- analysis.json
- metadata.json
- Reporte HTML
- Dashboard JMeter
- Dashboard Grafana

---

# Criterios de éxito

Una ejecución exitosa debe cumplir:

- Pipeline sin errores técnicos.
- Evidencias completas.
- SLA evaluado.
- Reporte generado.
- Dashboard actualizado.

---

# Criterios de fallo

Una ejecución puede fallar por:

- Error técnico.
- Error funcional.
- Incumplimiento de SLA.
- Falta de evidencias.

Estos escenarios deben distinguirse claramente.