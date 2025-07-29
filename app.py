# Sistema de Arquivologia - Backend Flask
# Versão corrigida e funcional

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

app = Flask(__name__)

# Permitir CORS para frontend local
CORS(app, resources={r"/*": {"origins": ["http://127.0.0.1:5500", "http://localhost:5500"]}})

# Configurar tipos MIME para vídeos
mimetypes.add_type('video/mp4', '.mp4')
mimetypes.add_type('video/webm', '.webm')
mimetypes.add_type('video/ogg', '.ogv')
mimetypes.add_type('video/avi', '.avi')
mimetypes.add_type('video/mov', '.mov')
mimetypes.add_type('video/wmv', '.wmv')

# Definição dos caminhos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAMINHO_USUARIOS = os.path.join(BASE_DIR, "usuarios.json")
CAMINHO_DADOS = os.path.join(BASE_DIR, "dados.json")
CAMINHO_LOGS = os.path.join(BASE_DIR, "logs.json")
CAMINHO_EXPORTACOES = os.path.join(BASE_DIR, "exportacoes.json")
PASTA_EXPORTS = os.path.join(BASE_DIR, "exports")
PASTA_UPLOADS = os.path.join(BASE_DIR, "uploads")

# Criar pastas necessárias
os.makedirs(PASTA_EXPORTS, exist_ok=True)
os.makedirs(PASTA_UPLOADS, exist_ok=True)

# Extensões permitidas
EXTENSOES_PERMITIDAS = {
    "png", "jpg", "jpeg", "gif", "bmp",
    "mp4", "avi", "mov", "wmv",
    "mp3", "wav", "ogg", "m4a",
    "pdf", "doc", "docx", "txt"
}

def arquivo_valido(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in EXTENSOES_PERMITIDAS

def carregar_usuarios():
    if os.path.exists(CAMINHO_USUARIOS):
        with open(CAMINHO_USUARIOS, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def salvar_usuarios(lista):
    with open(CAMINHO_USUARIOS, "w", encoding="utf-8") as f:
        json.dump(lista, f, indent=4, ensure_ascii=False)

def carregar_dados():
    if os.path.exists(CAMINHO_DADOS):
        with open(CAMINHO_DADOS, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def salvar_dados(lista):
    with open(CAMINHO_DADOS, "w", encoding="utf-8") as f:
        json.dump(lista, f, indent=4, ensure_ascii=False)

def carregar_logs():
    if os.path.exists(CAMINHO_LOGS):
        with open(CAMINHO_LOGS, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def salvar_logs(lista):
    with open(CAMINHO_LOGS, "w", encoding="utf-8") as f:
        json.dump(lista, f, indent=4, ensure_ascii=False)

def carregar_exportacoes():
    if os.path.exists(CAMINHO_EXPORTACOES):
        with open(CAMINHO_EXPORTACOES, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def salvar_exportacoes(lista):
    with open(CAMINHO_EXPORTACOES, "w", encoding="utf-8") as f:
        json.dump(lista, f, indent=4, ensure_ascii=False)

def registrar_log(usuario, acao, detalhes=""):
    logs = carregar_logs()
    novo_log = {
        "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
        "usuario": usuario,
        "acao": acao,
        "detalhes": detalhes,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    logs.append(novo_log)
    salvar_logs(logs)

def pode_modificar(tipo_usuario):
    return tipo_usuario in ["administrador", "editor"]

# ROTAS
@app.route("/login", methods=["POST"])
def login():
    data = request.json
    usuarios = carregar_usuarios()
    usuario_req = data.get("usuario")
    senha_req = data.get("senha", "").encode('utf-8')
    
    for user in usuarios:
        if user["usuario"] == usuario_req:
            senha_banco = user["senha"].encode('utf-8')
            if bcrypt.checkpw(senha_req, senha_banco):
                registrar_log(usuario_req, "LOGIN", "Login realizado com sucesso")
                return jsonify({"status": "ok", "tipo": user["tipo"]})
            else:
                registrar_log(usuario_req, "LOGIN_FALHOU", "Senha incorreta")
                return jsonify({"status": "erro", "mensagem": "Senha incorreta"})
    
    registrar_log(usuario_req or "desconhecido", "LOGIN_FALHOU", "Usuário não encontrado")
    return jsonify({"status": "erro", "mensagem": "Usuário não encontrado"})

@app.route("/cadastrar_usuario", methods=["POST"])
def cadastrar_usuario():
    data = request.json
    usuarios = carregar_usuarios()
    usuario_admin = data.get("usuario_admin", "")
    
    if any(u["usuario"] == data.get("usuario") for u in usuarios):
        return jsonify({"status": "erro", "mensagem": "Usuário já existe"})
    
    senha_hash = bcrypt.hashpw(data.get("senha", "").encode("utf-8"), bcrypt.gensalt())
    novo_usuario = {
        "usuario": data.get("usuario"),
        "senha": senha_hash.decode("utf-8"),
        "tipo": data.get("tipo")
    }
    usuarios.append(novo_usuario)
    salvar_usuarios(usuarios)
    
    registrar_log(usuario_admin, "CADASTRAR_USUARIO", f"Usuário {data.get('usuario')} cadastrado como {data.get('tipo')}")
    return jsonify({"status": "ok"})

@app.route("/salvar_dados", methods=["POST"])
def salvar_dados_doc():
    dados = carregar_dados()
    novo = request.json
    usuario = novo.get("usuario", "")
    
    if "id" not in novo:
        novo["id"] = datetime.now().strftime("%Y%m%d%H%M%S%f")
    
    if "arquivo_nome" not in novo:
        novo["arquivo_nome"] = ""
    
    dados.append(novo)
    salvar_dados(dados)
    
    registrar_log(usuario, "ADICIONAR_DOCUMENTO", f"Documento {novo.get('Arquivo', '')} adicionado")
    return jsonify({"status": "ok"})

@app.route("/ver_dados", methods=["GET"])
def ver_dados():
    """Rota para visualizar todos os documentos"""
    dados = carregar_dados()
    return jsonify(dados)

@app.route("/documentos", methods=["GET"])
def listar_documentos():
    return jsonify(carregar_dados())

@app.route("/ver_usuarios", methods=["GET"])
def ver_usuarios():
    return jsonify(carregar_usuarios())

@app.route("/excluir_usuario", methods=["POST"])
def excluir_usuario():
    data = request.json
    tipo_usuario = data.get("tipo_usuario", "")
    usuario_admin = data.get("usuario_admin", "")
    
    if not pode_modificar(tipo_usuario):
        return jsonify({"status": "erro", "mensagem": "Permissão negada para excluir usuário"})
    
    usuarios = carregar_usuarios()
    usuario_excluido = data.get("usuario")
    usuarios = [u for u in usuarios if u["usuario"] != usuario_excluido]
    salvar_usuarios(usuarios)
    
    registrar_log(usuario_admin, "EXCLUIR_USUARIO", f"Usuário {usuario_excluido} excluído")
    return jsonify({"status": "ok"})

@app.route("/excluir_documento", methods=["POST"])
def excluir_documento():
    data = request.json
    tipo_usuario = data.get("tipo_usuario", "")
    usuario = data.get("usuario", "")
    
    if not pode_modificar(tipo_usuario):
        return jsonify({"status": "erro", "mensagem": "Permissão negada para excluir documento"})
    
    dados = carregar_dados()
    doc_id = data.get("id")
    documento_excluido = next((d for d in dados if d.get("id") == doc_id), None)
    dados = [d for d in dados if d.get("id") != doc_id]
    salvar_dados(dados)
    
    if documento_excluido:
        registrar_log(usuario, "EXCLUIR_DOCUMENTO", f"Documento {documento_excluido.get('Arquivo', '')} excluído")
    
    return jsonify({"status": "ok"})

@app.route("/editar_documento", methods=["POST"])
def editar_documento():
    data = request.json
    tipo_usuario = data.get("tipo_usuario", "")
    usuario = data.get("usuario", "")
    
    if not pode_modificar(tipo_usuario):
        return jsonify({"status": "erro", "mensagem": "Permissão negada para editar documento"})
    
    if "original" not in data or "atualizado" not in data:
        return jsonify({"status": "erro", "mensagem": "Dados incompletos"})
    
    documentos = carregar_dados()
    original = data["original"]
    atualizado = data["atualizado"]
    
    for i, doc in enumerate(documentos):
        if doc.get("id") == original.get("id"):
            documentos[i] = atualizado
            salvar_dados(documentos)
            registrar_log(usuario, "EDITAR_DOCUMENTO", f"Documento {atualizado.get('Arquivo', '')} editado")
            return jsonify({"status": "ok", "mensagem": "Documento atualizado com sucesso"})
    
    return jsonify({"status": "erro", "mensagem": "Documento original não encontrado"})

@app.route("/exportar_excel", methods=["POST"])
def exportar_excel():
    dados = request.get_json()
    nome = request.args.get("nome", f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    usuario = request.args.get("usuario", "")
    
    if not nome.lower().endswith('.xlsx'):
        nome += ".xlsx"
    
    caminho_arquivo = os.path.join(PASTA_EXPORTS, nome)
    df = pd.DataFrame(dados)
    df.to_excel(caminho_arquivo, index=False)
    
    # Registrar exportação
    exportacoes = carregar_exportacoes()
    nova_exportacao = {
        "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
        "nome_arquivo": nome,
        "tipo": "Excel",
        "usuario": usuario,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "quantidade_documentos": len(dados),
        "dados": dados
    }
    exportacoes.append(nova_exportacao)
    salvar_exportacoes(exportacoes)
    
    registrar_log(usuario, "EXPORTAR_EXCEL", f"Exportação Excel: {nome} ({len(dados)} documentos)")
    
    return send_file(caminho_arquivo, as_attachment=True, download_name=nome)

@app.route("/exportar_word", methods=["POST"])
def exportar_word():
    dados = request.get_json()
    nome = request.args.get("nome", f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    usuario = request.args.get("usuario", "")
    
    if not nome.lower().endswith('.docx'):
        nome += ".docx"
    
    caminho_arquivo = os.path.join(PASTA_EXPORTS, nome)
    doc = Document()
    
    # Configurar orientação horizontal
    section = doc.sections[-1]
    section.orientation = WD_ORIENT.LANDSCAPE
    new_width, new_height = section.page_height, section.page_width
    section.page_width = new_width
    section.page_height = new_height
    
    doc.add_heading('Documentos Arquivísticos', level=1)
    
    if dados:
        # Criar tabela única com todos os documentos
        campos = list(dados[0].keys())
        campos = [c for c in campos if c not in ["arquivo_nome", "id", "usuario"]]
        
        table = doc.add_table(rows=1, cols=len(campos))
        table.style = 'Table Grid'
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        
        # Cabeçalho
        hdr_cells = table.rows[0].cells
        for i, campo in enumerate(campos):
            hdr_cells[i].text = str(campo)
        
        # Dados
        for item in dados:
            row_cells = table.add_row().cells
            for i, campo in enumerate(campos):
                row_cells[i].text = str(item.get(campo, ""))
        
        # Seção de arquivos de mídia
        doc.add_paragraph("")
        doc.add_heading('Arquivos de Mídia Associados', level=2)
        
        for item in dados:
            if "arquivo_nome" in item and item["arquivo_nome"]:
                nome_arquivo = item["arquivo_nome"]
                ext = nome_arquivo.split(".")[-1].lower()
                caminho_arquivo_midia = os.path.join(PASTA_UPLOADS, nome_arquivo)
                
                if os.path.exists(caminho_arquivo_midia):
                    doc.add_paragraph(f"Documento: {item.get('Arquivo', 'N/A')}")
                    if ext in ["png", "jpg", "jpeg", "bmp"]:
                        try:
                            doc.add_picture(caminho_arquivo_midia, width=Inches(3))
                        except:
                            doc.add_paragraph(f"Imagem: {nome_arquivo} (erro ao carregar)")
                    else:
                        doc.add_paragraph(f"Mídia: {nome_arquivo}")
                    doc.add_paragraph("")
    
    doc.save(caminho_arquivo)
    
    # Registrar exportação
    exportacoes = carregar_exportacoes()
    nova_exportacao = {
        "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
        "nome_arquivo": nome,
        "tipo": "Word",
        "usuario": usuario,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "quantidade_documentos": len(dados),
        "dados": dados
    }
    exportacoes.append(nova_exportacao)
    salvar_exportacoes(exportacoes)
    
    registrar_log(usuario, "EXPORTAR_WORD", f"Exportação Word: {nome} ({len(dados)} documentos)")
    
    return send_file(caminho_arquivo, as_attachment=True, download_name=nome)

@app.route("/upload_arquivo", methods=["POST"])
def upload_arquivo():
    if "arquivo" not in request.files:
        return jsonify({"status": "erro", "mensagem": "Nenhum arquivo enviado"})
    
    arquivo = request.files["arquivo"]
    usuario = request.form.get("usuario", "")
    
    if arquivo.filename == "":
        return jsonify({"status": "erro", "mensagem": "Nome do arquivo vazio"})
    
    if not arquivo_valido(arquivo.filename):
        return jsonify({"status": "erro", "mensagem": "Extensão de arquivo não permitida"})
    
    filename = secure_filename(arquivo.filename)
    caminho_salvar = os.path.join(PASTA_UPLOADS, filename)
    
    if os.path.exists(caminho_salvar):
        nome_base, ext = os.path.splitext(filename)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{nome_base}_{timestamp}{ext}"
        caminho_salvar = os.path.join(PASTA_UPLOADS, filename)
    
    arquivo.save(caminho_salvar)
    
    registrar_log(usuario, "UPLOAD_ARQUIVO", f"Arquivo {filename} enviado")
    
    return jsonify({"status": "ok", "mensagem": "Arquivo salvo com sucesso", "nome_arquivo": filename})

@app.route("/uploads/<filename>", methods=["GET"])
def baixar_arquivo(filename):
    try:
        caminho_arquivo = os.path.join(PASTA_UPLOADS, filename)
        if not os.path.exists(caminho_arquivo):
            return jsonify({"status": "erro", "mensagem": "Arquivo não encontrado"}), 404
        
        # Detectar tipo MIME
        mime_type, _ = mimetypes.guess_type(filename)
        
        return send_from_directory(
            PASTA_UPLOADS, 
            filename, 
            mimetype=mime_type,
            as_attachment=False,
            conditional=True
        )
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route("/listar_uploads", methods=["GET"])
def listar_uploads():
    try:
        arquivos = []
        for filename in os.listdir(PASTA_UPLOADS):
            caminho_arquivo = os.path.join(PASTA_UPLOADS, filename)
            if os.path.isfile(caminho_arquivo):
                stat = os.stat(caminho_arquivo)
                arquivos.append({
                    "nome": filename,
                    "tamanho": stat.st_size,
                    "data_modificacao": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                })
        return jsonify(arquivos)
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)})

@app.route("/excluir_upload", methods=["POST"])
def excluir_upload():
    data = request.json
    filename = data.get("filename")
    usuario = data.get("usuario", "")
    tipo_usuario = data.get("tipo_usuario", "")
    
    if not pode_modificar(tipo_usuario):
        return jsonify({"status": "erro", "mensagem": "Permissão negada"})
    
    try:
        caminho_arquivo = os.path.join(PASTA_UPLOADS, filename)
        if os.path.exists(caminho_arquivo):
            os.remove(caminho_arquivo)
            registrar_log(usuario, "EXCLUIR_UPLOAD", f"Arquivo {filename} excluído")
            return jsonify({"status": "ok"})
        else:
            return jsonify({"status": "erro", "mensagem": "Arquivo não encontrado"})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)})

@app.route("/ver_logs", methods=["GET"])
def ver_logs():
    return jsonify(carregar_logs())

@app.route("/ver_exportacoes", methods=["GET"])
def ver_exportacoes():
    return jsonify(carregar_exportacoes())

if __name__ == "__main__":
    app.run(debug=True)
