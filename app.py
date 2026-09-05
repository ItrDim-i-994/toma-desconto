import os
import secrets
import requests

from flask import Flask, redirect, request

app = Flask(__name__)

MELI_CLIENT_ID = os.getenv("MELI_CLIENT_ID")
MELI_CLIENT_SECRET = os.getenv("MELI_CLIENT_SECRET")

REDIRECT_URI = "https://toma-desconto.onrender.com/callback"

# Guardaremos temporariamente o state da autorização
oauth_states = set()


@app.route("/")
def home():
    return """
    <html>
        <head>
            <title>TOMA DESCONTO!</title>
        </head>
        <body>
            <h1>🔥 TOMA DESCONTO!</h1>
            <h2>Conexão com Mercado Livre</h2>

            <p>Servidor online.</p>

            <br>

            <a href="/mercadolivre">
                <button style="font-size:20px;padding:15px;">
                    🛒 Conectar Mercado Livre
                </button>
            </a>
        </body>
    </html>
    """


@app.route("/mercadolivre")
def mercadolivre():
    if not MELI_CLIENT_ID:
        return "Erro: MELI_CLIENT_ID não configurado no Render.", 500

    state = secrets.token_urlsafe(32)
    oauth_states.add(state)

    authorization_url = (
        "https://auth.mercadolivre.com.br/authorization"
        "?response_type=code"
        f"&client_id={MELI_CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&state={state}"
    )

    return redirect(authorization_url)


@app.route("/callback")
def callback():
    error = request.args.get("error")

    if error:
        return f"""
        <h1>❌ Autorização não concluída</h1>
        <p>Erro: {error}</p>
        """

    code = request.args.get("code")
    state = request.args.get("state")

    if not code:
        return """
        <h1>❌ Erro</h1>
        <p>O Mercado Livre não enviou o código de autorização.</p>
        """, 400

    if not state or state not in oauth_states:
        return """
        <h1>❌ Erro de segurança</h1>
        <p>O parâmetro state é inválido.</p>
        """, 400

    oauth_states.discard(state)

    if not MELI_CLIENT_SECRET:
        return """
        <h1>❌ Erro</h1>
        <p>MELI_CLIENT_SECRET não está configurado no Render.</p>
        """, 500

    response = requests.post(
        "https://api.mercadolibre.com/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": MELI_CLIENT_ID,
            "client_secret": MELI_CLIENT_SECRET,
            "code": code,
            "redirect_uri": REDIRECT_URI,
        },
        timeout=30,
    )

    if response.status_code != 200:
        return f"""
        <h1>❌ Erro ao obter Access Token</h1>
        <p>Status: {response.status_code}</p>
        <pre>{response.text}</pre>
        """, 500

    token_data = response.json()

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    user_id = token_data.get("user_id")

    # NÃO mostramos os tokens na tela.
    return f"""
    <html>
        <head>
            <title>TOMA DESCONTO - Mercado Livre</title>
        </head>
        <body>
            <h1>🎉 Mercado Livre conectado!</h1>

            <p>✅ OAuth funcionando.</p>
            <p>✅ Access Token recebido.</p>
            <p>✅ Refresh Token recebido.</p>
            <p>👤 Usuário autorizado: {user_id}</p>

            <hr>

            <p><strong>Próximo passo:</strong></p>
            <p>Vamos salvar a autorização de forma segura e testar a API.</p>
        </body>
    </html>
    """


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
