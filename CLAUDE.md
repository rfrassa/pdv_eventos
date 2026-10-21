# CONTEXTO
Principiante en código (Python, Django, Next, JS), fuerte en flujos de
negocio. Objetivo: arquitecto de software mediado por AI de talla mundial.
La AI ejecuta; yo decido y soy responsable.

---

# PRINCIPIOS DE ARQUITECTURA (el porqué de todo lo demás)

Estas 3 máximas gobiernan cada decisión. Las 6 reglas inviolables de abajo
son su aplicación concreta. Ante cualquier duda o conflicto entre skills,
recomendaciones o atajos: estas máximas mandan.

## Máxima 1 — La reversibilidad define el rigor
El recurso escaso es el criterio, no el tiempo. Gastalo donde la decisión
es difícil de deshacer: esquema de datos, contratos de API pública, modelo
de auth, datos fiscales/dinero. Ahí: lento, análisis de impacto, revisión.
Lo reversible (nombres, carpetas, librería de UI): rápido, se cambia después.
No invertir el rigor.
  → Reglas 1, 4, 6.

## Máxima 2 — El costo de un sistema es el costo de cambiarlo, no de construirlo
El software vive en mantenimiento. Toda decisión se juzga con una pregunta:
¿baja o sube el costo del PRÓXIMO cambio? Frena dos enemigos: sobre-ingeniería
(abstracciones que nadie pidió) y deuda silenciosa (atajos baratos hoy, caros
mañana). Abstracción que no reduce el costo de un cambio real = decoración.
Borrar.
  → Reglas 2, 5.

## Máxima 3 — Soy responsable de cada línea, la haya tipeado o no
Delegar ejecución no delega la responsabilidad. No se mergea lo que no se
puede explicar y defender línea por línea. La AI es rapidísima para estar
equivocada con confianza; el rol humano es el único criterio sobre negocio
y consecuencias en el loop. Código que no se entiende no está terminado:
es un pasivo sin explotar.
  → Reglas 3, 4.

---

# REGLAS INVIOLABLES (aplicación de las máximas)
# [RECONSTRUIDAS DE MEMORIA — verificar contra tu versión real]

1. Análisis de impacto obligatorio antes de modificar cualquier modelo
   Django. Identificar qué depende del modelo antes de tocarlo.
   ← aplica Máxima 1.

2. Deuda técnica siempre visible. Ningún atajo sin dejar registro explícito
   (TODO/comentario/issue). Nada de deuda escondida.
   ← aplica Máxima 2.

3. Nunca bugs silenciosos. Todo error se loguea o se propaga. Prohibido
   tragar excepciones (`except: pass`) o fallar sin dejar rastro.
   ← aplica Máxima 3.

4. Nunca correr migraciones en producción sin revisión explícita.
   ← aplica Máximas 1 y 3.

5. Siempre cambios pequeños e incrementales. Un cambio, un commit, un porqué.
   ← aplica Máxima 2.

6. Nunca tocar la integración AFIP sin protocolo de protección explícito.
   ← aplica Máxima 1.

Estas 6 reglas anulan cualquier recomendación de un skill de Superpowers.