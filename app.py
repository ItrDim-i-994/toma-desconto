import os
import secrets
import hashlib
import base64
import requests

from flask import Flask, redirect, request

app = Flask(__name__)

# ============================================================
# CONFIGURAÇÕES
# ============================================================

MELI_CLIENT_ID = os.getenv("MELI_CLIENT_ID")
MELI_CLIENT_SECRET = os.getenv("MELI_CLIENT_SECRET")

REDIRECT_URI = "https://toma-desconto.onrender.com/callback"

# Guarda temporariamente os dados do OAuth
oauth_states = {}


# ============================================================
# PÁGINA INICIAL
# ============================================================

@app.route("/")
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>TOMA DESCONTO!</title>
    </head>

    <body style="
        font-family: Arial;
        text-align: center;
        margin-top: 80px;
        background: #f5f5f5;
    ">

        <h1>🔥 TOMA DESCONTO!</h1>

        <h2>Conexão com Mercado Livre</h2>

        <p>Servidor online.</p>

        <br>

        <a href="/mercadolivre">
            <button style="
                font-size: 20px;
                padding: 15px 30px;
                cursor: pointer;
            ">
                🛒 Conectar Mercado Livre
            </button>
        </a>

    </body>
    </html>
    """


# ============================================================
# INICIAR AUTORIZAÇÃO MERCADO LIVRE
# ============================================================

@app.route("/mercadolivre")
def mercadolivre():

    if not MELI_CLIENT_ID:
        return """
        <h1>❌ Erro</h1>
        <p>MELI_CLIENT_ID não está configurado no Render.</p>
        """, 500

    if not MELI_CLIENT_SECRET:
        return """
        <h1>❌ Erro</h1>
        <p>MELI_CLIENT_SECRET não está configurado no Render.</p>
        """, 500

    # --------------------------------------------------------
    # 1. Criar STATE
    # --------------------------------------------------------

    state = secrets.token_urlsafe(32)

    # --------------------------------------------------------
    # 2. Criar CODE VERIFIER
    # --------------------------------------------------------

    code_verifier = secrets.token_urlsafe(64)

    # --------------------------------------------------------
    # 3. Criar CODE CHALLENGE
    # --------------------------------------------------------

    code_challenge_bytes = hashlib.sha256(
        code_verifier.encode("utf-8")
    ).digest()

    code_challenge = base64.urlsafe_b64encode(
        code_challenge_bytes
    ).decode("utf-8").rstrip("=")

    # --------------------------------------------------------
    # Guardar temporariamente
    # --------------------------------------------------------

    oauth_states[state] = {
        "code_verifier": code_verifier
    }

    # --------------------------------------------------------
    # URL DE AUTORIZAÇÃO
    # --------------------------------------------------------

    authorization_url = (
        "https://auth.mercadolivre.com.br/authorization"
        "?response_type=code"
        f"&client_id={MELI_CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&state={state}"
        f"&code_challenge={code_challenge}"
        "&code_challenge_method=S256"
    )

    return redirect(authorization_url)


# ============================================================
# CALLBACK
# ============================================================

@app.route("/callback")
def callback():

    # --------------------------------------------------------
    # Verificar se Mercado Livre retornou erro
    # --------------------------------------------------------

    error = request.args.get("error")

    if error:
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>TOMA DESCONTO</title>
        </head>

        <body style="font-family: Arial; text-align:center; margin-top:80px;">

            <h1>❌ Autorização não concluída</h1>

            <p>Erro retornado pelo Mercado Livre:</p>

            <pre>{error}</pre>

        </body>
        </html>
        """, 400

    # --------------------------------------------------------
    # Recuperar CODE
    # --------------------------------------------------------

    code = request.args.get("code")

    # --------------------------------------------------------
    # Recuperar STATE
    # --------------------------------------------------------

    state = request.args.get("state")

    if not code:
        return """
        <h1>❌ Erro</h1>
        <p>O Mercado Livre não enviou o código de autorização.</p>
        """, 400

    if not state:
        return """
        <h1>❌ Erro de segurança</h1>
        <p>O parâmetro state não foi recebido.</p>
        """, 400

    # --------------------------------------------------------
    # Verificar STATE
    # --------------------------------------------------------

    oauth_data = oauth_states.get(state)

    if not oauth_data:
        return """
        <h1>❌ Erro de segurança</h1>
        <p>O parâmetro state é inválido ou expirou.</p>
        """, 400

    # --------------------------------------------------------
    # Recuperar CODE VERIFIER
    # --------------------------------------------------------

    code_verifier = oauth_data["code_verifier"]

    # --------------------------------------------------------
    # Consumir STATE
    # --------------------------------------------------------

    oauth_states.pop(state, None)

    # --------------------------------------------------------
    # Verificar Client Secret
    # --------------------------------------------------------

    if not MELI_CLIENT_SECRET:
        return """
        <h1>❌ Erro</h1>
        <p>MELI_CLIENT_SECRET não está configurado no Render.</p>
        """, 500

    # --------------------------------------------------------
    # TROCAR CODE POR ACCESS TOKEN
    # --------------------------------------------------------

    response = requests.post(
        "https://api.mercadolibre.com/oauth/token",

        data={
            "grant_type": "authorization_code",
            "client_id": MELI_CLIENT_ID,
            "client_secret": MELI_CLIENT_SECRET,
            "code": code,
            "redirect_uri": REDIRECT_URI,

            # IMPORTANTE:
            # PKCE exige este parâmetro
            "code_verifier": code_verifier,
        },

        headers={
            "accept": "application/json",
            "content-type": "application/x-www-form-urlencoded",
        },

        timeout=30,
    )

    # --------------------------------------------------------
    # ERRO
    # --------------------------------------------------------

    if response.status_code != 200:

        return f"""
        <!DOCTYPE html>
        <html>

        <head>
            <meta charset="UTF-8">
            <title>Erro Mercado Livre</title>
        </head>

        <body style="font-family: Arial; text-align:center; margin-top:80px;">

            <h1>❌ Erro ao obter Access Token</h1>

            <p><strong>Status:</strong> {response.status_code}</p>

            <pre>{response.text}</pre>

        </body>

        </html>
        """, 500

    # --------------------------------------------------------
    # TOKEN RECEBIDO
    # --------------------------------------------------------

    token_data = response.json()

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    user_id = token_data.get("user_id")
    expires_in = token_data.get("expires_in")

    # --------------------------------------------------------
    # VERIFICAR TOKEN
    # --------------------------------------------------------

    if not access_token:

        return """
        <h1>❌ Erro</h1>
        <p>O Mercado Livre respondeu, mas não enviou Access Token.</p>
        """, 500

    # --------------------------------------------------------
    # TESTAR API
    # --------------------------------------------------------

    api_response = requests.get(
        "https://api.mercadolibre.com/users/me",
        headers={
            "Authorization": f"Bearer {access_token}"
        },
        timeout=30,
    )

    # --------------------------------------------------------
    # API FUNCIONOU
    # --------------------------------------------------------

    if api_response.status_code == 200:

        return f"""
        <!DOCTYPE html>

        <html>

        <head>
            <meta charset="UTF-8">

            <title>
                TOMA DESCONTO - Mercado Livre
            </title>
        </head>

        <body style="
            font-family: Arial;
            text-align: center;
            margin-top: 60px;
            background: #f5f5f5;
        ">

            <h1>🎉 Mercado Livre conectado!</h1>

            <h2>🔥 TOMA DESCONTO!</h2>

            <p>✅ OAuth funcionando</p>

            <p>✅ PKCE funcionando</p>

            <p>✅ Access Token recebido</p>

            <p>✅ Refresh Token recebido</p>

            <p>✅ API do Mercado Livre respondeu corretamente</p>

            <hr style="max-width:500px;">

            <p>
                👤 <strong>Usuário autorizado:</strong>
                {user_id}
            </p>

            <p>
                ⏱️ <strong>Token válido por:</strong>
                {expires_in} segundos
            </p>

            <br>

            <h3>🚀 Conexão concluída!</h3>

            <p>
                O TOMA DESCONTO já conseguiu conversar
                com a API do Mercado Livre.
            </p>

        </body>

        </html>
        """

    # --------------------------------------------------------
    # TOKEN RECEBIDO, MAS API FALHOU
    # --------------------------------------------------------

    return f"""
    <!DOCTYPE html>

    <html>

    <head>
        <meta charset="UTF-8">
        <title>TOMA DESCONTO</title>
    </head>

    <body style="
        font-family: Arial;
        text-align: center;
        margin-top: 60px;
    ">

        <h1>⚠️ Token recebido</h1>

        <p>O OAuth funcionou.</p>

        <p>
            Porém, o teste da API retornou:
        </p>

        <p>
            <strong>HTTP {api_response.status_code}</strong>
        </p>

        <pre>{api_response.text}</pre>

    </body>

    </html>
    """, 500


# ============================================================
# EXECUTAR LOCALMENTE
# ============================================================

if __name__ == "__main__":

    port = int(
        os.environ.get("PORT", 10000)
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
