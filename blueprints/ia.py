import os
import re

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func

from models import db, Category, State, Municipality, TouristProvider

ia_bp = Blueprint('ia', __name__, url_prefix='/ia')

from langchain_groq import ChatGroq
# Importaciones pesadas diferidas para acelerar el arranque del servidor
sql_db_instance = None

# Configuración de carpetas
DOCS_DIR = os.path.join(os.getcwd(), 'docs_normativa')
VECTOR_DB_DIR = os.path.join(os.getcwd(), 'vector_db')

# Inicializar lector de OCR (esto descarga modelos la primera vez)
reader = None
global_vectorstore = None

def get_ocr_reader():
    global reader
    if reader is None:
        import easyocr
        reader = easyocr.Reader(['es'])
    return reader

# Modelo de embeddings y LLM optimizados (API vs Local)
embeddings_model = None
llm_model = None

def get_embeddings_model():
    global embeddings_model
    if embeddings_model is None:
        # Hemos vuelto al modelo local porque la API Key de Google arrojó 404 para embeddings. 
        # Al estar cargado globalmente igual será rápido en caché.
        from langchain_huggingface import HuggingFaceEmbeddings
        embeddings_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    return embeddings_model

def get_llm_model():
    global llm_model
    if llm_model is None:
        api_key = os.environ.get('GROQ_API_KEY')
        if api_key:
            # Seleccionamos llama-3.3-70b por ser el modelo actual soportado en Groq
            llm_model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0, api_key=api_key)
    return llm_model

def get_sql_db():
    global sql_db_instance
    if sql_db_instance is None:
        from langchain_community.utilities import SQLDatabase
        
        # En Flask con SQLite, lo más fiable es la ruta relativa al root
        db_uri = "sqlite:///instance/sig_inatur.db"
        
        try:
            sql_db_instance = SQLDatabase.from_uri(db_uri)
            detectadas = sql_db_instance.get_usable_table_names()
            print(f"\n--- [IA DIAGNÓSTICO] Tablas encontradas: {detectadas} ---")
            
            if not detectadas:
                print("--- [ALERTA] La IA no ve tablas. Verificando archivo... ---")
        except Exception as e:
            print(f"--- [ERROR CONEXIÓN SQL] {str(e)} ---")
            raise e
            
    return sql_db_instance

def get_vector_store():
    global global_vectorstore
    """Carga o crea la base de datos vectorial."""

    if global_vectorstore is not None:
        return global_vectorstore

    from langchain_community.vectorstores import FAISS
    from langchain_community.document_loaders import TextLoader, DirectoryLoader, PyPDFLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    model = get_embeddings_model()
    if os.path.exists(os.path.join(VECTOR_DB_DIR, "index.faiss")):
        global_vectorstore = FAISS.load_local(VECTOR_DB_DIR, model, allow_dangerous_deserialization=True)
        return global_vectorstore
    
    # Si no existe, indexar documentos
    loader = DirectoryLoader(DOCS_DIR, glob="./*.txt", loader_cls=TextLoader, loader_kwargs={'encoding': 'utf-8'})
    documents = loader.load()
    
    # También PDFs si los hay
    pdf_loader = DirectoryLoader(DOCS_DIR, glob="./*.pdf", loader_cls=PyPDFLoader)
    documents.extend(pdf_loader.load())
    
    if not documents:
        return None
        
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    texts = text_splitter.split_documents(documents)
    
    global_vectorstore = FAISS.from_documents(texts, model)
    global_vectorstore.save_local(VECTOR_DB_DIR)
    return global_vectorstore

@ia_bp.route('/chat')
@login_required
def chat():
    """Vista principal del chatbot."""
    return render_template('ia/chat.html')

@ia_bp.route('/ask', methods=['POST'])
@login_required
def ask():
    """Procesa una pregunta del usuario usando IA Híbrida (RAG o Agente SQL)."""
    query = request.json.get('question')
    if not query:
        return jsonify({'error': 'No se recibió ninguna pregunta.'}), 400
        
    try:
        llm = get_llm_model()
        if not llm:
            return jsonify({'answer': 'La API Key de Groq no está configurada.'})

        user_name = current_user.name if current_user.is_authenticated else "Usuario"
        user_role = current_user.role if current_user.is_authenticated else "Visitante"

        # 1. Agente Inteligente de Decisión (Ruteo Rápido)
        # El LLM deduce si la pregunta requiere buscar de manera RAG (textos/leyes) o en la Base de Datos (estadística)
        router_prompt = f"""
        El usuario ({user_role}) te hizo esta pregunta: "{query}"
        Responde estrictamente con "SQL" si la pregunta menciona contar, totalizar, buscar prestadores, RTN, RIF, categorías turísticas, hoteles, posadas, usuarios, o datos del sistema.
        Responde estrictamente con "LEY" si la pregunta es teórica, sobre normativas legales, derechos, deberes, o funcionamiento de INATUR teórico.
        Responde estrictamente con "GENERAL" si solo está saludando o preguntando quién eres.
        """
        decision = llm.invoke(router_prompt).content.strip().upper()

        if "SQL" in decision:
            # FLUJO: Análisis de Base de Datos en Tiempo Real
            from langchain_community.agent_toolkits import create_sql_agent
            
            sql_db = get_sql_db()
            agent_executor = create_sql_agent(llm, db=sql_db, verbose=True, max_iterations=5)
            
            # Contexto especial de seguridad y formato de idioma (Forzar Español en el Agente)
            sql_instructions = f"""
            Eres un analista de datos experto del sistema INATUR. 
            Usuario: {user_name}
            Pregunta: {query}
            
            TABLAS DISPONIBLES:
            - tourist_providers: Contiene los prestadores de servicio, su RTN, RIF, estatus (activo/vencido) y fecha de vencimiento (valid_until).
            - categories: Categorías turísticas (Hoteles, Posadas, etc).
            - municipalities: Municipios.
            - states: Estados.
            
            REGLAS:
            1. Ejecuta solo consultas SELECT. No intentes modificar la base de datos.
            2. Si preguntan por RTN vencidos, busca en tourist_providers donde status = 'vencido'.
            3. Responde siempre en ESPAÑOL VENEZOLANO.
            4. Se breve pero preciso.
            """
            
            sql_response = agent_executor.invoke({"input": sql_instructions})
            return jsonify({
                'answer': sql_response.get("output", "Disculpa, no pude obtener esa información de la base de datos."),
                'context_snippets': ["Consulta en Base de Datos SIG-INATUR (SQL) en tiempo real."]
            })
            
        elif "GENERAL" in decision:
            return jsonify({
                'answer': f"¡Hola {user_name}! Soy el Asistente Inteligente del SIG-INATUR. Estoy aquí para ayudarte tanto con consultas sobre la Base de Datos de Prestadores (cuántos hoteles hay, estatus del RTN, estadísticas) como con consultas sobre las Leyes y Normativas de INATUR. ¿Qué deseas revisar hoy?",
                'context_snippets': ["Asistencia Inicial del Sistema"]
            })

        # FLUJO: RAG (Base de Conocimiento de Texto y Leyes)
        vectorstore = get_vector_store()
        if not vectorstore:
            return jsonify({'answer': 'No hay documentos cargados en la base de conocimiento para responder a nivel legal.'})
            
        docs = vectorstore.similarity_search(query, k=3)
        context = "\n---\n".join([doc.page_content for doc in docs])
        
        prompt = f"""
        Eres el Asistente Inteligente Oficial del sistema SIG-INATUR.
        Estás hablando con {user_name}, su rol es: {user_role.upper()}.
        Tu función es responder estas cuestiones normativas basándote ESTRICTAMENTE en los siguientes extractos de la ley.
        
        CONTEXTO LEGAL:
        {context}
        
        PREGUNTA DEL USUARIO ({user_role.upper()}):
        {query}
        """
        
        response = llm.invoke(prompt)

        return jsonify({
            'answer': response.content,
            'context_snippets': [doc.page_content for doc in docs]
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@ia_bp.route('/reindex', methods=['POST'])
@login_required
def reindex():
    """Refresca la base de datos vectorial."""
    global global_vectorstore
    try:
        if os.path.exists(os.path.join(VECTOR_DB_DIR, "index.faiss")):
            os.remove(os.path.join(VECTOR_DB_DIR, "index.faiss"))
            os.remove(os.path.join(VECTOR_DB_DIR, "index.pkl"))
            
        global_vectorstore = None
        get_vector_store()
        return jsonify({'message': 'Índice de conocimiento actualizado correctamente.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@ia_bp.route('/insights', methods=['GET'])
@login_required
def insights():
    """Genera un reporte analítico basado en los datos actuales."""
    # Estadísticas básicas
    total_providers = TouristProvider.query.count()
    active_providers = TouristProvider.query.filter_by(status='activo').count()
    vencidos = TouristProvider.query.filter_by(status='vencido').count()
    
    # Distribución por categoría (Top 3)
    categories_stats = db.session.query(Category.name, func.count(TouristProvider.id))\
        .join(TouristProvider)\
        .group_by(Category.name)\
        .order_by(func.count(TouristProvider.id).desc())\
        .limit(3).all()
        
    # Auditoría: Detectar RIFs duplicados
    duplicates = db.session.query(TouristProvider.rif, func.count(TouristProvider.id))\
        .group_by(TouristProvider.rif)\
        .having(func.count(TouristProvider.id) > 1).all()
        
    # Generar "Insight" textual (Simulación de análisis IA)
    insights_text = []
    
    if total_providers > 0:
        health_score = (active_providers / total_providers) * 100
        if health_score > 80:
            insights_text.append(f"La base de datos muestra una salud operativa excelente ({health_score:.1f}% activos).")
        elif health_score > 50:
            insights_text.append(f"Se observa una proporción moderada de prestadores activos ({health_score:.1f}%).")
        else:
            insights_text.append(f"ALERTA: Menos del 50% de los prestadores están activos. Se requiere jornada de actualización.")

        if categories_stats:
            top_cat = categories_stats[0][0]
            insights_text.append(f"El sector predominante es '{top_cat}', lo que sugiere una oportunidad para diversificar servicios en otras áreas.")
            
        if vencidos > 0:
            insights_text.append(f"Hay {vencidos} prestadores con RTN vencido que deberían ser notificados para renovación inmediata.")
            
        if duplicates:
            insights_text.append(f"ANOMALÍA DETECTADA: Se encontraron {len(duplicates)} números de RIF duplicados. Se recomienda auditoría de integridad.")
    else:
        insights_text.append("No hay datos suficientes para generar insights estratégicos aún.")

    return jsonify({
        'summary': " ".join(insights_text),
        'stats': {
            'total': total_providers,
            'active_pct': (active_providers / total_providers * 100) if total_providers > 0 else 0,
            'vencidos': vencidos,
            'anomalies': len(duplicates)
        }
    })
