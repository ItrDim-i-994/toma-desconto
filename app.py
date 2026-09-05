import os
import secrets
import hashlib
import base64
import requests

from flask import Flask, redirect, request, make_response

app = Flask(__name__)

# ============================================================
# CONFIGURAÇÕES
# ============================================================

MELI_CLIENT_ID = os.getenv("MELI_CLIENT_ID")
MELI_CLIENT_SECRET = os.getenv("MELI_CLIENT_SECRET")

REDIRECT_URI = "https://toma-desconto.onrender.com/callback"


# ============================================================
# FUNÇÕES PKCE
# ============================================================

def gerar_code_verifier():
    """
    Gera o código secreto usado pelo PKCE.
    """
    return secrets.token_urlsafe(64)


def gerar_code_challenge(code_verifier):
    """
    Gera o code_challenge a partir do code_verifier.
    """

    digest = hashlib.sha256(
        code_verifier.encode("utf-8")
    ).digest()

    return base64.urlsafe_b64encode(
        digest
    ).decode("utf-8").rstrip("=")


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
# INICIAR OAUTH
# ============================================================

@app.route("/mercadolivre")
def mercadolivre():

    # --------------------------------------------------------
    # Verificar Client ID
    # --------------------------------------------------------

    if not MELI_CLIENT_ID:

        return """
        <h1>❌ Erro</h1>

        <p>
        MELI_CLIENT_ID não está configurado no Render.
        </p>
        """, 500

    # --------------------------------------------------------
    # Verificar Client Secret
    # --------------------------------------------------------

    if not MELI_CLIENT_SECRET:

        return """
        <h1>❌ Erro</h1>

        <p>
        MELI_CLIENT_SECRET não está configurado no Render.
        </p>
        """, 500

    # --------------------------------------------------------
    # GERAR STATE
    # --------------------------------------------------------

    state = secrets.token_urlsafe(32)

    # --------------------------------------------------------
    # GERAR CODE VERIFIER
    # --------------------------------------------------------

    code_verifier = gerar_code_verifier()

    # --------------------------------------------------------
    # GERAR CODE CHALLENGE
    # --------------------------------------------------------

    code_challenge = gerar_code_challenge(
        code_verifier
    )

    # --------------------------------------------------------
    # URL DO MERCADO LIVRE
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

    # --------------------------------------------------------
    # Criar resposta
    # --------------------------------------------------------

    response = make_response(
        redirect(authorization_url)
    )

    # --------------------------------------------------------
    # Guardar os dados do PKCE em cookie
    # --------------------------------------------------------

    response.set_cookie(
        "oauth_state",
        state,
        max_age=600,
        secure=True,
        httponly=True,
        samesite="Lax"
    )

    response.set_cookie(
        "oauth_code_verifier",
        code_verifier,
        max_age=600,
        secure=True,
        httponly=True,
        samesite="Lax"
    )

    return response


# ============================================================
# CALLBACK DO MERCADO LIVRE
# ============================================================

@app.route("/callback")
def callback():

    # --------------------------------------------------------
    # Verificar erro
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

        <body style="
            font-family: Arial;
            text-align: center;
            margin-top: 80px;
        ">

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

    if not code:

        return """
        <h1>❌ Erro</h1>

        <p>
        O Mercado Livre não enviou o código de autorização.
        </p>
        """, 400

    # --------------------------------------------------------
    # Recuperar STATE enviado pelo Mercado Livre
    # --------------------------------------------------------

    state_recebido = request.args.get("state")

    # --------------------------------------------------------
    # Recuperar STATE salvo no navegador
    # --------------------------------------------------------

    state_salvo = request.cookies.get("oauth_state")

    # --------------------------------------------------------
    # Validar STATE
    # --------------------------------------------------------

    if not state_recebido:

        return """
        <h1>❌ Erro de segurança</h1>

        <p>
        O Mercado Livre não enviou o parâmetro state.
        </p>
        """, 400

    if not state_salvo:

        return """
        <h1>❌ Erro de segurança</h1>

        <p>
        O navegador não possui o state da autorização.
        </p>

        <p>
        Comece novamente pelo botão
        <strong>Conectar Mercado Livre</strong>.
        </p>
        """, 400

    if not secrets.compare_digest(
        state_recebido,
        state_salvo
    ):

        return """
        <h1>❌ Erro de segurança</h1>

        <p>
        O parâmetro state não corresponde à autorização iniciada.
        </p>

        <p>
        Comece novamente pelo botão
        <strong>Conectar Mercado Livre</strong>.
        </p>
        """, 400

    # --------------------------------------------------------
    # Recuperar CODE VERIFIER
    # --------------------------------------------------------

    code_verifier = request.cookies.get(
        "oauth_code_verifier"
    )

    if not code_verifier:

        return """
        <h1>❌ Erro de segurança</h1>

        <p>
        O code_verifier do PKCE não foi encontrado.
        </p>

        <p>
        Comece novamente pelo botão
        <strong>Conectar Mercado Livre</strong>.
        </p>
        """, 400

    # --------------------------------------------------------
    # Verificar Client Secret
    # --------------------------------------------------------

    if not MELI_CLIENT_SECRET:

        return """
        <h1>❌ Erro</h1>

        <p>
        MELI_CLIENT_SECRET não está configurado no Render.
        </p>
        """, 500

    # ========================================================
    # TROCAR CODE POR TOKEN
    # ========================================================

    response = requests.post(

        "https://api.mercadolibre.com/oauth/token",

        data={

            "grant_type":
                "authorization_code",

            "client_id":
                MELI_CLIENT_ID,

            "client_secret":
                MELI_CLIENT_SECRET,

            "code":
                code,

            "redirect_uri":
                REDIRECT_URI,

            "code_verifier":
                code_verifier,
        },

        headers={
            "accept": "application/json",
            "content-type":
                "application/x-www-form-urlencoded",
        },

        timeout=30,
    )

    # ========================================================
    # ERRO AO PEGAR TOKEN
    # ========================================================

    if response.status_code != 200:

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
            margin-top: 70px;
        ">

            <h1>❌ Erro ao obter Access Token</h1>

            <p>
                <strong>Status:</strong>
                {response.status_code}
            </p>

            <pre>
{response.text}
            </pre>

        </body>

        </html>
        """, 500

    # ========================================================
    # TOKEN RECEBIDO
    # ========================================================

    token_data = response.json()

    access_token = token_data.get(
        "access_token"
    )

    refresh_token = token_data.get(
        "refresh_token"
    )

    user_id = token_data.get(
        "user_id"
    )

    expires_in = token_data.get(
        "expires_in"
    )

    # --------------------------------------------------------
    # Verificar Access Token
    # --------------------------------------------------------

    if not access_token:

        return """
        <h1>❌ Erro</h1>

        <p>
        O Mercado Livre respondeu,
        mas não enviou Access Token.
        </p>
        """, 500

    # ========================================================
    # TESTAR API
    # ========================================================

    api_response = requests.get(

        "https://api.mercadolibre.com/users/me",

        headers={
            "Authorization":
                f"Bearer {access_token}"
        },

        timeout=30,
    )

    # ========================================================
    # API FUNCIONOU
    # ========================================================

    if api_response.status_code == 200:

        # ----------------------------------------------------
        # Limpar cookies
        # ----------------------------------------------------

        resposta = make_response(
            f"""
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

                <h1>
                    🎉 Mercado Livre conectado!
                </h1>

                <h2>
                    🔥 TOMA DESCONTO!
                </h2>

                <p>
                    ✅ OAuth funcionando
                </p>

                <p>
                    ✅ PKCE funcionando
                </p>

                <p>
                    ✅ Access Token recebido
                </p>

                <p>
                    ✅ Refresh Token recebido
                </p>

                <p>
                    ✅ API do Mercado Livre respondeu corretamente
                </p>

                <hr style="max-width:500px;">

                <p>
                    👤
                    <strong>Usuário autorizado:</strong>
                    {user_id}
                </p>

                <p>
                    ⏱️
                    <strong>Token válido por:</strong>
                    {expires_in} segundos
                </p>

                <br>

                <h3>
                    🚀 CONEXÃO CONCLUÍDA!
                </h3>

                <p>
                    O TOMA DESCONTO conseguiu
                    conversar com a API do Mercado Livre.
                </p>

                <p>
                    🔎 Agora podemos partir para
                    a busca automática de produtos.
                </p>

            </body>

            </html>
            """
        )

        resposta.delete_cookie(
            "oauth_state"
        )

        resposta.delete_cookie(
            "oauth_code_verifier"
        )

        return resposta

    # ========================================================
    # TOKEN RECEBIDO MAS API FALHOU
    # ========================================================

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

        <p>
            O OAuth funcionou.
        </p>

        <p>
            Porém, o teste da API retornou:
        </p>

        <h2>
            HTTP {api_response.status_code}
        </h2>

        <pre>
{api_response.text}
        </pre>

    </body>

    </html>
    """, 500


# ============================================================
# EXECUÇÃO
# ============================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
