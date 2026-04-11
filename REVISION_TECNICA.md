# Revisión Integral del Proyecto: SIG-INATUR (Python/Flask)

Este documento detalla el estado actual, la arquitectura y las capacidades tecnológicas del sistema **SIG-INATUR**, una migración avanzada desde Laravel hacia un ecosistema moderno basado en Python.

## 1. Arquitectura del Sistema
El proyecto utiliza una arquitectura modular basada en **Flask Blueprints** (Carpeta `blueprints/`), lo que facilita el mantenimiento y la escalabilidad.

- **Núcleo (`app.py`):** Configura la aplicación, la base de datos (SQLAlchemy), las migraciones y el sistema de autenticación.
- **Modelos (`models.py`):** Esquema relacional optimizado para la gestión turística, incluyendo auditoría (`created_by`, `updated_by`).
- **Módulos (Blueprints):**
    - `auth`: Gestión de seguridad y sesiones.
    - `dashboard`: Visualización de métricas críticas mediante Chart.js.
    - `providers`: Módulo central de gestión del Registro Turístico Nacional (RTN).
    - `ia`: El componente más avanzado, integrando modelos de lenguaje y bases vectoriales.
    - `admin`: Herramientas de respaldo (Postgres/SQLite) y mantenimiento.
    - `reports`: Motor de generación de documentos institucionales (FPDF2).

## 2. Implementación de Inteligencia Artificial (IA)
El módulo `ia.py` destaca por su enfoque híbrido, utilizando **LangChain**:

- **Ruteo Inteligente (Decision Agent):** El sistema analiza la intención del usuario para decidir si consultar la base de datos (SQL) o buscar en la normativa legal (RAG).
- **Chatbot RAG:** Utiliza **FAISS** como base de datos vectorial local. Combina documentos PDF y TXT de `docs_normativa`.
- **Agente SQL:** Implementa `create_sql_agent` para permitir consultas en lenguaje natural directamente sobre los datos de los prestadores.
- **AI Insights:** Genera informes estratégicos automáticos detectando anomalías (ej. RIFs duplicados) y salud operativa.

## 3. Estado de la Interfaz de Usuario (UI/UX)
El frontend implementa una estética **premium**:
- **Tipografía:** Inter (Google Fonts) para alta legibilidad.
- **Layout:** Sidebar fija con diseño responsivo.
- **Componentes:** Tarjetas con sombreados suaves y micro-animaciones en botones.
- **Interactividad:** Gráficos dinámicos (Doughnut, Pie, Bar) que reflejan el estado del RTN en tiempo real.

## 4. Hallazgos y Observaciones Técnicas

### ⚠️ Versión del Modelo Gemini
En `blueprints/ia.py` (Línea 53), se hace referencia a `gemini-2.5-flash`. Dado que las versiones actuales son 1.5 o 2.0 (experimental), se recomienda verificar este parámetro para evitar errores de conexión con la API de Google.

### 🔄 Fallback de Embeddings
El sistema está configurado para usar `HuggingFaceEmbeddings` (`all-MiniLM-L6-v2`) localmente debido a errores previos con la API de Google. Esto es una buena práctica de resiliencia que garantiza el funcionamiento offline o ante fallos de API.

### 🖼️ OCR (EasyOCR)
El motor de OCR está inicializado pero no se observa actualmente una ruta activa en los templates que permita la subida de documentos para este fin. Es un área lista para expansión.

## 5. Próximos Pasos Recomendados
1. **Validación de API Key:** Asegurar que las variables de entorno para Gemini estén actualizadas.
2. **Expansión de OCR:** Crear una vista en `ia/ocr.html` para permitir el escaneo automático de certificados de RIF/RTN.
3. **Optimización de Indexación:** Implementar un disparador (trigger) para que la base vectorial se actualice automáticamente al subir nuevos documentos a `docs_normativa`.

---
*Este reporte sirve como base para la validación final de la tesis y la puesta en marcha del sistema.*
