// Sistema de Arquivologia - JavaScript Principal
// Versão corrigida e funcional

let documentos = [] // variável global para armazenar documentos carregados
const selecionados = new Set() // conjunto para controlar seleção de múltiplos docs
let QRCode // Declaração da variável QRCode

// Função para renderizar a tabela de documentos
function renderTabela(documentos) {
  const tbody = document.querySelector("#tabelaDocumentos tbody")
  tbody.innerHTML = ""
  documentos.forEach((doc) => {
    const tr = document.createElement("tr")
    tr.innerHTML = `
      <td>${doc.id}</td>
      <td>${doc.titulo}</td>
      <td>${doc.autor}</td>
      <td>${doc.data}</td>
    `
    tbody.appendChild(tr)
  })
}

// === SISTEMA DE TEMA ===
function initTheme() {
  const savedTheme = localStorage.getItem("theme") || "light"
  document.documentElement.setAttribute("data-theme", savedTheme)
  updateThemeButton(savedTheme)
}

function toggleTheme() {
  const currentTheme = document.documentElement.getAttribute("data-theme")
  const newTheme = currentTheme === "dark" ? "light" : "dark"
  document.documentElement.setAttribute("data-theme", newTheme)
  localStorage.setItem("theme", newTheme)
  updateThemeButton(newTheme)
}

function updateThemeButton(theme) {
  const button = document.getElementById("theme-toggle")
  if (button) {
    button.textContent = theme === "dark" ? "☀️" : "🌙"
  }
}

// Inicializar tema
document.addEventListener("DOMContentLoaded", () => {
  initTheme()
  const themeButton = document.getElementById("theme-toggle")
  if (themeButton) {
    themeButton.addEventListener("click", toggleTheme)
  }
})

// === 1. CARREGAR DOCUMENTOS ===
async function carregarDocumentos() {
  try {
    const resposta = await fetch("http://localhost:5000/ver_dados")
    if (!resposta.ok) {
      throw new Error(`HTTP error! status: ${resposta.status}`)
    }
    documentos = await resposta.json()
    console.log("Documentos carregados:", documentos) // Debug
    renderTabela(documentos)
  } catch (e) {
    console.error("Erro ao carregar documentos:", e)
    alert("Erro ao carregar documentos: " + e.message)
  }
}

// === 2. LOGIN ===
function login() {
  const usuario = document.getElementById("usuario").value
  const senha = document.getElementById("senha").value
  fetch("http://localhost:5000/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ usuario, senha }),
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.status === "ok") {
        // Salvar usuário logado
        localStorage.setItem("usuarioLogado", usuario)
        localStorage.setItem("tipoUsuario", data.tipo)
        // Redireciona conforme tipo do usuário
        if (data.tipo === "administrador") {
          window.location = "admin.html"
        } else if (data.tipo === "editor") {
          window.location = "editor.html"
        } else if (data.tipo === "codificador") {
          window.location = "codificador.html"
        } else {
          window.location = "index.html" // fallback
        }
      } else {
        alert(data.mensagem || "Erro no login")
      }
    })
    .catch(() => alert("Erro na comunicação com o servidor."))
}

// === 3. CADASTRAR USUÁRIO ===
if (document.getElementById("formUsuario")) {
  document.getElementById("formUsuario").addEventListener("submit", function (e) {
    e.preventDefault()
    const usuario = this.usuario.value.trim()
    const senha = this.senha.value.trim()
    const tipo = this.tipo.value.trim()
    if (!usuario || !senha || !tipo) {
      alert("Preencha todos os campos.")
      return
    }
    fetch("http://localhost:5000/cadastrar_usuario", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        usuario,
        senha,
        tipo,
        usuario_admin: localStorage.getItem("usuarioLogado") || "admin",
      }),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.status === "ok") {
          alert("Usuário cadastrado com sucesso!")
          this.reset()
        } else {
          alert(data.mensagem || "Erro ao cadastrar usuário.")
        }
      })
      .catch(() => alert("Erro na comunicação com o servidor."))
  })
}

// === 4. SALVAR DADOS ===
if (document.getElementById("formDados")) {
  document.getElementById("formDados").addEventListener("submit", function (e) {
    e.preventDefault()
    const formData = new FormData(this)
    const obj = {}
    formData.forEach((v, k) => (obj[k] = v))
    // Adicionar arquivo se foi feito upload
    const arquivoNome = document.getElementById("arquivo_nome_salvo")
    if (arquivoNome && arquivoNome.value) {
      obj.arquivo_nome = arquivoNome.value
    }
    // Adicionar usuário que está salvando
    obj.usuario = localStorage.getItem("usuarioLogado") || "usuario"
    fetch("http://localhost:5000/salvar_dados", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(obj),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.status === "ok") {
          alert("Dados salvos com sucesso!")
          this.reset()
          if (arquivoNome) arquivoNome.value = ""
        } else {
          alert(data.mensagem || "Erro ao salvar dados.")
        }
      })
      .catch(() => alert("Erro na comunicação com o servidor."))
  })
}

// === 5. EXCLUIR USUÁRIO ===
if (window.location.pathname.includes("excluir_usuarios.html")) {
  fetch("http://localhost:5000/ver_usuarios")
    .then((res) => res.json())
    .then((usuarios) => {
      const tbody = document.querySelector("#tabelaUsuarios tbody")
      tbody.innerHTML = ""
      usuarios.forEach((user) => {
        const tr = document.createElement("tr")
        tr.innerHTML = `
        <td>${user.usuario}</td>
        <td>${user.tipo}</td>
        <td><button onclick="excluirUsuario('${user.usuario}')">Excluir</button></td>
      `
        tbody.appendChild(tr)
      })
    })
    .catch(() => alert("Erro ao carregar usuários."))
}

function excluirUsuario(usuario) {
  if (!confirm(`Deseja realmente excluir o usuário ${usuario}?`)) return
  fetch("http://localhost:5000/excluir_usuario", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      usuario,
      tipo_usuario: localStorage.getItem("tipoUsuario"),
      usuario_admin: localStorage.getItem("usuarioLogado") || "admin",
    }),
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.status === "ok") {
        alert("Usuário excluído com sucesso!")
        location.reload()
      } else {
        alert("Erro ao excluir usuário: " + data.mensagem)
      }
    })
    .catch(() => alert("Erro na comunicação com o servidor."))
}

// === 6. LOGOUT ===
function logout() {
  localStorage.clear()
  window.location = "index.html"
}

// === 7. BOTÃO VOLTAR ===
if (document.getElementById("btnVoltar")) {
  document.getElementById("btnVoltar").addEventListener("click", () => {
    const tipoUsuario = localStorage.getItem("tipoUsuario")
    if (tipoUsuario === "administrador") {
      window.location.href = "admin.html"
    } else if (tipoUsuario === "editor") {
      window.location.href = "editor.html"
    } else if (tipoUsuario === "codificador") {
      window.location.href = "codificador.html"
    } else {
      window.location.href = "index.html"
    }
  })
}
