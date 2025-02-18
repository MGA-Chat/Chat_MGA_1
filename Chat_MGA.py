import streamlit as st
import os
import json
import requests
import pandas as pd
from datetime import datetime
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain.vectorstores import FAISS
from langchain.embeddings.huggingface import HuggingFaceEmbeddings
import openai  # Para chamar GPT-4

# 🚀 Configuração Inicial
st.set_page_config(page_title="Chatbot MGA Project", layout="wide")

# 🔒 **Autenticação**
AUTHORIZED_USERS = {
    "userPT": {"password": "passwordPT", "team": "Equipe_1"},
    "userROU": {"password": "passwordROU", "team": "Equipe_2"},
    "userBE": {"password": "passwordBE", "team": "Equipe_3"},
    "userIT": {"password": "passwordIT", "team": "Equipe_4"},
    "userPL": {"password": "passwordPL", "team": "Equipe_5"},
}

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
    st.session_state["user_team"] = None

if not st.session_state["authenticated"]:
    st.sidebar.subheader("🔒 Login Required")
    username = st.sidebar.text_input("Username")
    password = st.sidebar.text_input("Password", type="password")

    if st.sidebar.button("Login"):
        if username in AUTHORIZED_USERS and AUTHORIZED_USERS[username]["password"] == password:
            st.session_state["authenticated"] = True
            st.session_state["user_team"] = AUTHORIZED_USERS[username]["team"]
            st.sidebar.success(f"✅ Acesso permitido! Bem-vindo, {st.session_state['user_team']}.")
            st.experimental_rerun()
        else:
            st.sidebar.error("❌ Credenciais inválidas!")

    st.stop()

# 📂 Diretório dos Arquivos (Google Drive)
base_dir = "Chatbot_Files"
team_dirs = {team: os.path.join(base_dir, team) for team in AUTHORIZED_USERS.values()}

# Criar diretórios se não existirem
for directory in team_dirs.values():
    os.makedirs(directory, exist_ok=True)

# 📂 **Upload de Arquivos**
st.sidebar.subheader("📄 Upload Files")
uploaded_files = st.sidebar.file_uploader("", type=["pdf", "docx", "txt", "xlsx", "csv"], accept_multiple_files=True)

if uploaded_files:
    for uploaded_file in uploaded_files:
        ext = uploaded_file.name.split(".")[-1].lower()
        save_dir = team_dirs[st.session_state["user_team"]]  # Salvar na pasta da equipe
        file_path = os.path.join(save_dir, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
    st.sidebar.success("📄 Arquivo(s) carregado(s) com sucesso!")

# 📚 **Carregar Arquivos de Todas as Equipes**
@st.cache_data
def load_documents(files):
    documents = []
    for file_name in files:
        file_path = os.path.join(team_dirs[st.session_state["user_team"]], file_name)
        if file_name.endswith(".pdf"):
            loader = PyPDFLoader(file_path)
            documents.extend(loader.load())
        elif file_name.endswith(".docx"):
            loader = Docx2txtLoader(file_path)
            documents.extend(loader.load())
        elif file_name.endswith(".txt"):
            loader = TextLoader(file_path)
            documents.extend(loader.load())
        elif file_name.endswith((".xlsx", ".csv")):
            df = pd.read_excel(file_path) if file_name.endswith(".xlsx") else pd.read_csv(file_path)
            text_content = "\n".join(df.astype(str).apply(lambda x: " | ".join(x), axis=1))
            documents.append(text_content)
    return documents

selected_files = os.listdir(team_dirs[st.session_state["user_team"]])  # Selecionar arquivos da equipe
documents = load_documents(selected_files)

# ✅ Verificar se documentos foram carregados
if not documents:
    st.error("Nenhum documento carregado. Verifique os arquivos.")
    st.stop()

# 🔎 **Processar Arquivos**
text_splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=50)
texts = text_splitter.split_documents(documents)

# ✅ Criar Vetor de Busca FAISS
vectorstore = FAISS.from_documents(texts, HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2"))

# 💬 **Entrada de Pergunta**
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

query = st.chat_input("💬 Pergunte sobre os arquivos:")

if query:
    try:
        results = vectorstore.similarity_search(query, k=3)
        context = "\n".join([f"- {doc[:300]}..." for doc in results])

        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Você é um assistente especializado em responder perguntas sobre documentos."},
                {"role": "user", "content": f"Baseado nos seguintes documentos:\n{context}\n\nPergunta: {query}"}
            ]
        )

        chatbot_response = response["choices"][0]["message"]["content"]
        st.session_state.chat_history.append({"role": "bot", "content": chatbot_response})
        st.write("### 🎯 Resposta:")
        st.success(chatbot_response)

    except Exception as e:
        st.error(f"Erro ao processar: {e}")
