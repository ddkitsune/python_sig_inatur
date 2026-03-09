import os
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from langchain_community.document_loaders import PyPDFLoader, TextLoader, DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from models import Category, State, Municipality, TouristProvider
from sqlalchemy import func
import easyocr
import numpy as np
import cv2
import re

ia_bp = Blueprint('ia', __name__, url_prefix='/ia')

# Configuración de carpetas
DOCS_DIR = os.path.join(os.getcwd(), 'docs_normativa')
VECTOR_DB_DIR = os.path.join(os.getcwd(), 'vector_db')

# Inicializar lector de OCR (esto descarga modelos la primera vez)
reader = None

def get_ocr_reader():
    global reader
    if reader is None:
        reader = easyocr.Reader(['es'])
    return reader

# Modelo de embeddings (ligero)
embeddings_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

def get_vector_store():
    """Carga o crea la base de datos vectorial."""
    if os.path.exists(os.path.join(VECTOR_DB_DIR, "index.faiss")):
        return FAISS.load_local(VECTOR_DB_DIR, embeddings_model, allow_dangerous_deserialization=True)
    
    # Si no existe, indexar documentos
    loader = DirectoryLoader(DOCS_DIR, glob="./*.txt", loader_cls=TextLoader)
    documents = loader.load()
    
    # También PDFs si los hay
    pdf_loader = DirectoryLoader(DOCS_DIR, glob="./*.pdf", loader_cls=PyPDFLoader)
    documents.extend(pdf_loader.load())
    
    if not documents:
        return None
        
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    texts = text_splitter.split_documents(documents)
    
    vectorstore = FAISS.from_documents(texts, embeddings_model)
    vectorstore.save_local(VECTOR_DB_DIR)
    return vectorstore

@ia_bp.route('/chat')
@login_required
def chat():
    """Vista principal del chatbot."""
    return render_template('ia/chat.html')

@ia_bp.route('/ask', methods=['POST'])
@login_required
def ask():
    """Procesa una pregunta del usuario usando RAG."""
    query = request.json.get('question')
    if not query:
        return jsonify({'error': 'No se recibió ninguna pregunta.'}), 400
        
    try:
        vectorstore = get_vector_store()
        if not vectorstore:
            return jsonify({'answer': 'No hay documentos cargados en la base de conocimiento para responder.'})
            
        # Similitud de búsqueda (Retrieval)
        docs = vectorstore.similarity_search(query, k=3)
        context = "\n---\n".join([doc.page_content for doc in docs])
        
        # En una implementación real con API Key, aquí se enviaría el contexto al LLM.
        # Por ahora, simulamos la respuesta estructurada basándonos en el RAG.
        return jsonify({
            'answer': f"Basándome en la normativa institucional, encontré lo siguiente:\n\n{docs[0].page_content[:300]}...",
            'context_snippets': [doc.page_content for doc in docs]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@ia_bp.route('/reindex', methods=['POST'])
@login_required
def reindex():
    """Refresca la base de datos vectorial."""
    try:
        if os.path.exists(os.path.join(VECTOR_DB_DIR, "index.faiss")):
            os.remove(os.path.join(VECTOR_DB_DIR, "index.faiss"))
            os.remove(os.path.join(VECTOR_DB_DIR, "index.pkl"))
            
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
