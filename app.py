from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import os
import json
import bcrypt
import pandas as pd
from docx import Document
from datetime import datetime
from werkzeug.utils import secure_filename
from docx.shared import Inches
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
import mimetypes
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# CORS configuration
CORS(app, resources={
    r"/*": {
        "origins": [
            "http://127.0.0.1:5500", 
            "http://localhost:5500",
            "http://localhost:3000",
            "https://*.onrender.com",
            "https://*.vercel.app"
        ]
    }
})

# Configure MIME types for videos
mimetypes.add_type('video/mp4', '.mp4')
mimetypes.add_type('video/webm', '.webm')
mimetypes.add_type('video/ogg', '.ogv')
mimetypes.add_type('video/avi', '.avi')
mimetypes.add_type('video/mov', '.mov')
mimetypes.add_type('video/wmv', '.wmv')

# Try to import PostgreSQL, fallback to JSON files if not available
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    import psycopg2.pool
    POSTGRES_AVAILABLE = True
    logger.info("PostgreSQL support available")
except ImportError as e:
    logger.warning(f"PostgreSQL not available: {e}. Using JSON files as fallback.")
    POSTGRES_AVAILABLE = False

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and POSTGRES_AVAILABLE:
    try:
        db_pool = psycopg2.pool.SimpleConnectionPool(
            1, 20,
            DATABASE_URL,
            cursor_factory=RealDictCursor
        )
        logger.info("Database connection pool created successfully")
    except Exception as e:
        logger.error(f"Error creating database pool: {e}")
        db_pool = None
        POSTGRES_AVAILABLE = False
else:
    db_pool = None
    POSTGRES_AVAILABLE = False

# Path definitions
BASE_DIR = Path(__file__).parent.absolute()
DATA_DIR = BASE_DIR / "data"
EXPORTS_DIR = BASE_DIR / "exports"
UPLOADS_DIR = BASE_DIR / "uploads"

# Create necessary directories
DATA_DIR.mkdir(exist_ok=True)
EXPORTS_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(exist_ok=True)

# File paths for JSON fallback
USERS_FILE = DATA_DIR / "usuarios.json"
DOCUMENTS_FILE = DATA_DIR / "dados.json"
LOGS_FILE = DATA_DIR / "logs.json"
EXPORTS_FILE = DATA_DIR / "exportacoes.json"

# Allowed extensions
ALLOWED_EXTENSIONS = {
    "png", "jpg", "jpeg", "gif", "bmp",
    "mp4", "avi", "mov", "wmv",
    "mp3", "wav", "ogg", "m4a",
    "pdf", "doc", "docx", "txt"
}

# Maximum file size (16MB)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

def load_json_file(filepath, default=None):
    """Safely load JSON file with error handling"""
    if default is None:
        default = []
    
    try:
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading {filepath}: {e}")
    
    return default

def save_json_file(filepath, data):
    """Safely save JSON file with error handling"""
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return True
    except IOError as e:
        logger.error(f"Error saving {filepath}: {e}")
        return False

def get_db_connection():
    """Get database connection from pool"""
    if POSTGRES_AVAILABLE and db_pool:
        return db_pool.getconn()
    return None

def return_db_connection(conn):
    """Return connection to pool"""
    if POSTGRES_AVAILABLE and db_pool and conn:
        db_pool.putconn(conn)

def init_database():
    """Initialize database tables or JSON files"""
    if POSTGRES_AVAILABLE:
        return init_postgres_database()
    else:
        return init_json_files()

def init_postgres_database():
    """Initialize PostgreSQL database tables"""
    conn = get_db_connection()
    if not conn:
        logger.error("No database connection available")
        return False
    
    try:
        cur = conn.cursor()
        
        # Create users table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                usuario VARCHAR(100) UNIQUE NOT NULL,
                senha VARCHAR(255) NOT NULL,
                tipo VARCHAR(50) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create documents table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id VARCHAR(50) PRIMARY KEY,
                data JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create logs table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id VARCHAR(50) PRIMARY KEY,
                usuario VARCHAR(100),
                acao VARCHAR(100),
                detalhes TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create exports table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS exports (
                id VARCHAR(50) PRIMARY KEY,
                nome_arquivo VARCHAR(255),
                tipo VARCHAR(50),
                usuario VARCHAR(100),
                quantidade_documentos INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        logger.info("PostgreSQL database tables initialized successfully")
        
        # Create default admin user if not exists
        cur.execute("SELECT COUNT(*) FROM users WHERE usuario = %s", ('admin',))
        if cur.fetchone()['count'] == 0:
            admin_password = bcrypt.hashpw("admin123".encode("utf-8"), bcrypt.gensalt())
            cur.execute("""
                INSERT INTO users (usuario, senha, tipo) 
                VALUES (%s, %s, %s)
            """, ('admin', admin_password.decode("utf-8"), 'administrador'))
            conn.commit()
            logger.info("Default admin user created: admin/admin123")
        
        return True
        
    except Exception as e:
        logger.error(f"Error initializing PostgreSQL database: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        return_db_connection(conn)

def init_json_files():
    """Initialize JSON files with default admin user"""
    try:
        users = load_json_file(USERS_FILE, [])
        if not users:
            admin_password = bcrypt.hashpw("admin123".encode("utf-8"), bcrypt.gensalt())
            default_admin = {
                "usuario": "admin",
                "senha": admin_password.decode("utf-8"),
                "tipo": "administrador",
                "created_at": datetime.now().isoformat()
            }
            save_json_file(USERS_FILE, [default_admin])
            logger.info("Default admin user created in JSON: admin/admin123")
        
        # Initialize other files
        load_json_file(DOCUMENTS_FILE, [])
        load_json_file(LOGS_FILE, [])
        load_json_file(EXPORTS_FILE, [])
        
        logger.info("JSON files initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Error initializing JSON files: {e}")
        return False

def is_valid_file(filename):
    """Check if file has valid extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def log_action(user, action, details=""):
    """Log user actions"""
    if POSTGRES_AVAILABLE:
        log_action_postgres(user, action, details)
    else:
        log_action_json(user, action, details)

def log_action_postgres(user, action, details=""):
    """Log user actions to PostgreSQL"""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cur = conn.cursor()
        log_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
        cur.execute("""
            INSERT INTO logs (id, usuario, acao, detalhes) 
            VALUES (%s, %s, %s, %s)
        """, (log_id, user, action, details))
        conn.commit()
        logger.info(f"Action logged to PostgreSQL: {user} - {action}")
    except Exception as e:
        logger.error(f"Error logging action to PostgreSQL: {e}")
        conn.rollback()
    finally:
        cur.close()
        return_db_connection(conn)

def log_action_json(user, action, details=""):
    """Log user actions to JSON file"""
    try:
        logs = load_json_file(LOGS_FILE, [])
        new_log = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
            "usuario": user,
            "acao": action,
            "detalhes": details,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        logs.append(new_log)
        
        # Keep only last 1000 logs
        if len(logs) > 1000:
            logs = logs[-1000:]
        
        save_json_file(LOGS_FILE, logs)
        logger.info(f"Action logged to JSON: {user} - {action}")
    except Exception as e:
        logger.error(f"Error logging action to JSON: {e}")

def can_modify(user_type):
    """Check if user can modify data"""
    return user_type in ["administrador", "editor"]

# Routes
@app.route("/", methods=["GET"])
def home():
    """API documentation endpoint"""
    storage_type = "PostgreSQL" if POSTGRES_AVAILABLE and db_pool else "JSON Files"
    return jsonify({
        "name": "Sistema de Arquivologia API",
        "version": "3.1.0",
        "status": "running",
        "storage": storage_type,
        "endpoints": {
            "authentication": ["/login", "/cadastrar_usuario"],
            "documents": ["/documentos", "/ver_dados", "/salvar_dados", "/editar_documento", "/excluir_documento"],
            "files": ["/upload_arquivo", "/uploads/<filename>", "/listar_uploads", "/excluir_upload"],
            "exports": ["/exportar_excel", "/exportar_word", "/ver_exportacoes"],
            "admin": ["/ver_usuarios", "/excluir_usuario", "/ver_logs"]
        }
    })

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    storage_status = "PostgreSQL connected" if (POSTGRES_AVAILABLE and db_pool) else "JSON files"
    return jsonify({
        "status": "healthy",
        "storage": storage_status,
        "timestamp": datetime.now().isoformat(),
        "directories": {
            "data": DATA_DIR.exists(),
            "exports": EXPORTS_DIR.exists(),
            "uploads": UPLOADS_DIR.exists()
        }
    })

@app.route("/login", methods=["POST"])
def login():
    """User login endpoint"""
    data = request.json
    if not data or not data.get("usuario") or not data.get("senha"):
        return jsonify({"status": "erro", "mensagem": "Usuário e senha são obrigatórios"}), 400
    
    if POSTGRES_AVAILABLE:
        return login_postgres(data)
    else:
        return login_json(data)

def login_postgres(data):
    """Login using PostgreSQL"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "erro", "mensagem": "Erro de conexão com banco"}), 500
    
    try:
        cur = conn.cursor()
        cur.execute("SELECT senha, tipo FROM users WHERE usuario = %s", (data.get("usuario"),))
        user = cur.fetchone()
        
        if user and bcrypt.checkpw(data.get("senha").encode('utf-8'), user['senha'].encode('utf-8')):
            log_action(data.get("usuario"), "LOGIN", "Login realizado com sucesso")
            return jsonify({"status": "ok", "tipo": user['tipo']})
        else:
            log_action(data.get("usuario", "desconhecido"), "LOGIN_FALHOU", "Credenciais inválidas")
            return jsonify({"status": "erro", "mensagem": "Credenciais inválidas"}), 401
            
    except Exception as e:
        logger.error(f"Error in PostgreSQL login: {e}")
        return jsonify({"status": "erro", "mensagem": "Erro interno"}), 500
    finally:
        cur.close()
        return_db_connection(conn)

def login_json(data):
    """Login using JSON files"""
    try:
        users = load_json_file(USERS_FILE, [])
        username = data.get("usuario")
        password = data.get("senha", "").encode('utf-8')
        
        for user in users:
            if user["usuario"] == username:
                stored_password = user["senha"].encode('utf-8')
                if bcrypt.checkpw(password, stored_password):
                    log_action(username, "LOGIN", "Login realizado com sucesso")
                    return jsonify({"status": "ok", "tipo": user["tipo"]})
                else:
                    log_action(username, "LOGIN_FALHOU", "Senha incorreta")
                    return jsonify({"status": "erro", "mensagem": "Credenciais inválidas"}), 401
        
        log_action(username or "desconhecido", "LOGIN_FALHOU", "Usuário não encontrado")
        return jsonify({"status": "erro", "mensagem": "Credenciais inválidas"}), 401
        
    except Exception as e:
        logger.error(f"Error in JSON login: {e}")
        return jsonify({"status": "erro", "mensagem": "Erro interno"}), 500

@app.route("/cadastrar_usuario", methods=["POST"])
def register_user():
    """Register new user endpoint"""
    data = request.json
    if not data or not all(k in data for k in ["usuario", "senha", "tipo"]):
        return jsonify({"status": "erro", "mensagem": "Dados incompletos"}), 400
    
    if POSTGRES_AVAILABLE:
        return register_user_postgres(data)
    else:
        return register_user_json(data)

def register_user_postgres(data):
    """Register user using PostgreSQL"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "erro", "mensagem": "Erro de conexão com banco"}), 500
    
    try:
        cur = conn.cursor()
        
        # Check if user exists
        cur.execute("SELECT COUNT(*) FROM users WHERE usuario = %s", (data.get("usuario"),))
        if cur.fetchone()['count'] > 0:
            return jsonify({"status": "erro", "mensagem": "Usuário já existe"}), 409
        
        # Hash password and insert user
        password_hash = bcrypt.hashpw(data.get("senha").encode("utf-8"), bcrypt.gensalt())
        cur.execute("""
            INSERT INTO users (usuario, senha, tipo) 
            VALUES (%s, %s, %s)
        """, (data.get("usuario"), password_hash.decode("utf-8"), data.get("tipo")))
        
        conn.commit()
        log_action(data.get("usuario_admin", "system"), "CADASTRAR_USUARIO", 
                  f"Usuário {data.get('usuario')} cadastrado como {data.get('tipo')}")
        
        return jsonify({"status": "ok", "mensagem": "Usuário cadastrado com sucesso"})
        
    except Exception as e:
        logger.error(f"Error registering user in PostgreSQL: {e}")
        conn.rollback()
        return jsonify({"status": "erro", "mensagem": "Erro ao cadastrar usuário"}), 500
    finally:
        cur.close()
        return_db_connection(conn)

def register_user_json(data):
    """Register user using JSON files"""
    try:
        users = load_json_file(USERS_FILE, [])
        username = data.get("usuario")
        
        # Check if user already exists
        if any(u["usuario"] == username for u in users):
            return jsonify({"status": "erro", "mensagem": "Usuário já existe"}), 409
        
        # Hash password
        password_hash = bcrypt.hashpw(data.get("senha", "").encode("utf-8"), bcrypt.gensalt())
        
        new_user = {
            "usuario": username,
            "senha": password_hash.decode("utf-8"),
            "tipo": data.get("tipo"),
            "created_at": datetime.now().isoformat()
        }
        
        users.append(new_user)
        
        if save_json_file(USERS_FILE, users):
            log_action(data.get("usuario_admin", "system"), "CADASTRAR_USUARIO", 
                      f"Usuário {username} cadastrado como {data.get('tipo')}")
            return jsonify({"status": "ok", "mensagem": "Usuário cadastrado com sucesso"})
        else:
            return jsonify({"status": "erro", "mensagem": "Erro ao salvar usuário"}), 500
            
    except Exception as e:
        logger.error(f"Error registering user in JSON: {e}")
        return jsonify({"status": "erro", "mensagem": "Erro ao cadastrar usuário"}), 500

@app.route("/ver_usuarios", methods=["GET"])
def list_users():
    """List all users endpoint"""
    if POSTGRES_AVAILABLE:
        return list_users_postgres()
    else:
        return list_users_json()

def list_users_postgres():
    """List users from PostgreSQL"""
    conn = get_db_connection()
    if not conn:
        return jsonify([])
    
    try:
        cur = conn.cursor()
        cur.execute("SELECT usuario, tipo, created_at FROM users ORDER BY created_at")
        users = cur.fetchall()
        return jsonify([dict(user) for user in users])
    except Exception as e:
        logger.error(f"Error listing users from PostgreSQL: {e}")
        return jsonify([])
    finally:
        cur.close()
        return_db_connection(conn)

def list_users_json():
    """List users from JSON files"""
    try:
        users = load_json_file(USERS_FILE, [])
        # Remove password hashes from response
        safe_users = [{k: v for k, v in user.items() if k != "senha"} for user in users]
        return jsonify(safe_users)
    except Exception as e:
        logger.error(f"Error listing users from JSON: {e}")
        return jsonify([])

@app.route("/ver_dados", methods=["GET"])
def view_data():
    """View all documents endpoint"""
    if POSTGRES_AVAILABLE:
        return view_data_postgres()
    else:
        return view_data_json()

def view_data_postgres():
    """View documents from PostgreSQL"""
    conn = get_db_connection()
    if not conn:
        return jsonify([])
    
    try:
        cur = conn.cursor()
        cur.execute("SELECT data FROM documents ORDER BY created_at")
        documents = cur.fetchall()
        return jsonify([doc['data'] for doc in documents])
    except Exception as e:
        logger.error(f"Error listing documents from PostgreSQL: {e}")
        return jsonify([])
    finally:
        cur.close()
        return_db_connection(conn)

def view_data_json():
    """View documents from JSON files"""
    try:
        return jsonify(load_json_file(DOCUMENTS_FILE, []))
    except Exception as e:
        logger.error(f"Error listing documents from JSON: {e}")
        return jsonify([])

@app.route("/documentos", methods=["GET"])
def list_documents():
    """List all documents endpoint (alias)"""
    return view_data()

@app.route("/ver_logs", methods=["GET"])
def view_logs():
    """View logs endpoint"""
    if POSTGRES_AVAILABLE:
        return view_logs_postgres()
    else:
        return view_logs_json()

def view_logs_postgres():
    """View logs from PostgreSQL"""
    conn = get_db_connection()
    if not conn:
        return jsonify([])
    
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM logs ORDER BY timestamp DESC LIMIT 100")
        logs = cur.fetchall()
        return jsonify([dict(log) for log in logs])
    except Exception as e:
        logger.error(f"Error listing logs from PostgreSQL: {e}")
        return jsonify([])
    finally:
        cur.close()
        return_db_connection(conn)

def view_logs_json():
    """View logs from JSON files"""
    try:
        return jsonify(load_json_file(LOGS_FILE, []))
    except Exception as e:
        logger.error(f"Error listing logs from JSON: {e}")
        return jsonify([])

# Error handlers
@app.errorhandler(413)
def too_large(e):
    return jsonify({"status": "erro", "mensagem": "Arquivo muito grande"}), 413

@app.errorhandler(404)
def not_found(e):
    return jsonify({"status": "erro", "mensagem": "Endpoint não encontrado"}), 404

@app.errorhandler(500)
def internal_error(e):
    logger.error(f"Internal server error: {e}")
    return jsonify({"status": "erro", "mensagem": "Erro interno do servidor"}), 500

if __name__ == "__main__":
    # Initialize database or JSON files
    if init_database():
        logger.info("Storage initialized successfully")
    else:
        logger.error("Failed to initialize storage")
    
    # Get port from environment or default to 5000
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
