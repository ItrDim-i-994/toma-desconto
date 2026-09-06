import os
import secrets
import hashlib
import base64
import requests
import psycopg2

from flask import Flask, redirect, request, make_response

app = Flask(__name__)

# ============================================================
# CONFIGURAÇÕES
# ============================================================

MELI_CLIENT_ID = os.getenv("MELI_CLIENT_ID")
MELI_CLIENT_SECRET = os.getenv("MELI_CLIENT_SECRET")

DATABASE_URL = os.getenv("DATABASE_URL")

REDIRECT_URI = "https://toma-desconto.onrender.com/callback"

TOKEN_URL = "https://api.mercadolibre.com/oauth/token"

# ============================================================
# BANCO DE DADOS
# ============================================================

def conectar_banco():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL não configurada.")

    return psycopg2.connect(DATABASE_URL)


def criar_tabela():

    conn = conectar_banco()

    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mercado_livre_tokens (
            id INTEGER PRIMARY KEY,
            user_id BIGINT,
            access_token TEXT NOT NULL,
            refresh_token TEXT NOT NULL,
            expires_at BIGINT NOT NULL,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()

    cursor.close()
    conn.close()


# ============================================================
# SALVAR TOKEN
# ============================================================

def salvar_tokens(
    user_id,
    access_token,
    refresh_token,
    expires_in
):

    import time

    expires_at = int(time.time()) + int(expires_in)

    conn = conectar_banco()

    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO mercado_livre_tokens
        (
            id,
            user_id,
            access_token,
            refresh_token,
            expires_at
        )
        VALUES
        (
            1,
            %s,
            %s,
            %s,
            %s
        )

        ON CONFLICT (id)

        DO UPDATE SET
            user_id = EXCLUDED.user_id,
            access_token = EXCLUDED.access_token,
            refresh_token = EXCLUDED.refresh_token,
            expires_at = EXCLUDED.expires_at,
            atualizado_em = CURRENT_TIMESTAMP;
    """, (
        user_id,
        access_token,
        refresh_token,
        expires_at
    ))

    conn.commit()

    cursor.close()
    conn.close()


# ============================================================
# RECUPERAR TOKEN
# ============================================================

def obter_tokens():

    conn = conectar_banco()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            user_id,
            access_token,
            refresh_token,
            expires_at
        FROM mercado_livre_tokens
        WHERE id = 1;
    """)

    resultado = cursor.fetchone()

    cursor.close()
    conn.close()

    return resultado


# ============================================================
# RENOVAR TOKEN
# ============================================================

def renovar_access_token():

    tokens = obter_tokens()

    if not tokens:
        return None

    user_id = tokens[0]
    refresh_token = tokens[2]

    if not refresh_token:
        return None

    response = requests.post(

        TOKEN_URL,

        data={
            "grant_type": "refresh_token",
            "client_id": MELI_CLIENT_ID,
            "client_secret": MELI_CLIENT_SECRET,
            "refresh_token": refresh_token,
        },

        headers={
            "accept": "application/json",
            "content-type":
                "application/x-www-form-urlencoded",
        },

        timeout=30,
    )

    if response.status_code != 200:

        print(
            "ERRO AO RENOVAR TOKEN:",
            response.status_code,
            response.text
        )

        return None

    token_data = response.json()

    novo_access_token = token_data.get(
        "access_token"
    )

    novo_refresh_token = token_data.get(
        "refresh_token"
    )

    novo_user_id = token_data.get(
        "user_id",
        user_id
    )

    expires_in = token_data.get(
        "expires_in"
    )

    if not novo_access_token:
        return None

    if not novo_refresh_token:
        print(
            "ERRO: Mercado Livre não enviou novo refresh token."
        )
        return None

    salvar_tokens(

        novo_user_id,

        novo_access_token,

        novo_refresh_token,

        expires_in
    )

    print(
        "TOKEN RENOVADO COM SUCESSO."
    )

    return novo_access_token


# ============================================================
# OBTER ACCESS TOKEN VÁLIDO
# ============================================================

def obter_access_token():

    tokens = obter_tokens()

    if not tokens:
        return None

    access_token = tokens[1]
    expires_at = tokens[3]

    import time

    agora = int(time.time())

    # Renovar quando faltar menos de 5 minutos
    if agora >= expires_at - 300:

        print(
            "Access Token próximo do vencimento."
        )

        return renovar_access_token()

    return access_token


# ============================================================
# BUSCAR PRODUTOS NO MERCADO LIVRE
# ============================================================

def buscar_produtos_mercado_livre(query, limit=20):

    access_token = obter_access_token()

    if not access_token:
        raise Exception("Não foi possível obter um Access Token válido.")

    url = "https://api.mercadolibre.com/sites/MLB/search"

    parametros = {
        "q": query,
        "limit": limit
    }

    resposta = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {access_token}"
        },
        params=parametros,
        timeout=30
    )

    if resposta.status_code != 200:
        raise Exception(
            f"Erro na busca do Mercado Livre: "
            f"{resposta.status_code} - {resposta.text}"
        )

    return resposta.json()
# ============================================================
# PKCE
# ============================================================

def gerar_code_verifier():

    return secrets.token_urlsafe(64)


def gerar_code_challenge(code_verifier):

    digest = hashlib.sha256(
        code_verifier.encode("utf-8")
    ).digest()

    return base64.urlsafe_b64encode(
        digest
    ).decode("utf-8").rstrip("=")


# ============================================================
# HOME
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

        <h2>🤖 Sistema de Ofertas</h2>

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

        <br><br>

        <a href="/status">

            <button style="
                font-size: 16px;
                padding: 10px 20px;
                cursor: pointer;
            ">

                🔎 Ver status

            </button>

        </a>

    </body>

    </html>
    """

# ============================================================
# BUSCAR PRODUTOS
# ============================================================

@app.route("/buscar")
def buscar():

    produto = request.args.get("produto", "").strip()

    if not produto:
        return """
        <!DOCTYPE html>
        <html>

        <head>
            <meta charset="UTF-8">
            <title>TOMA DESCONTO!</title>
        </head>

        <body style="
            font-family: Arial;
            background: #f5f5f5;
            padding: 30px;
        ">

            <h1>🔥 TOMA DESCONTO!</h1>

            <h2>🔎 Busca de produtos</h2>

            <p>
                Informe o produto que deseja pesquisar.
            </p>

            <p>
                Exemplo:
            </p>

            <code>
                /buscar?produto=air%20fryer
            </code>

        </body>

        </html>
        """

    try:

        dados = buscar_produtos_mercado_livre(
            produto,
            limit=20
        )

        resultados = dados.get(
            "results",
            []
        )

        html = f"""
        <!DOCTYPE html>
        <html>

        <head>
            <meta charset="UTF-8">
            <title>TOMA DESCONTO!</title>
        </head>

        <body style="
            font-family: Arial;
            background: #f5f5f5;
            padding: 30px;
        ">

            <h1>🔥 TOMA DESCONTO!</h1>

            <h2>🔎 Resultado da busca</h2>

            <p>
                Produto pesquisado:
                <strong>{produto}</strong>
            </p>

            <p>
                Anúncios encontrados:
                <strong>{len(resultados)}</strong>
            </p>

            <hr>
        """

        for i, produto_data in enumerate(
            resultados,
            start=1
        ):

            titulo = produto_data.get(
                "title",
                "Sem título"
            )

            preco = produto_data.get(
                "price",
                0
            )

            moeda = produto_data.get(
                "currency_id",
                "BRL"
            )

            link = produto_data.get(
                "permalink",
                "#"
            )

            item_id = produto_data.get(
                "id",
                ""
            )

            html += f"""
            <div style="
                background: white;
                padding: 20px;
                margin: 15px 0;
                border-radius: 10px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.10);
            ">

                <h3>
                    {i}. {titulo}
                </h3>

                <p>
                    🆔 ID:
                    <strong>{item_id}</strong>
                </p>

                <p>
                    💰 Preço:
                    <strong>{moeda} {preco}</strong>
                </p>

                <p>
                    🔗
                    <a
                        href="{link}"
                        target="_blank"
                        rel="noopener noreferrer"
                    >
                        Ver anúncio
                    </a>
                </p>

            </div>
            """

        html += """
        </body>
        </html>
        """

        return html

    except Exception as e:

        return f"""
        <!DOCTYPE html>

        <html>

        <body style="
            font-family: Arial;
            padding: 30px;
        ">

            <h1>❌ Erro na busca</h1>

            <pre>{e}</pre>

        </body>

        </html>
        """, 500
# ============================================================
# STATUS
# ============================================================

@app.route("/status")
def status():

    try:

        tokens = obter_tokens()

        if not tokens:

            return """
            <h1>⚠️ Mercado Livre não conectado</h1>

            <p>
            Nenhum token foi encontrado no banco.
            </p>

            <a href="/mercadolivre">
            Conectar Mercado Livre
            </a>
            """

        access_token = obter_access_token()

        if not access_token:

            return """
            <h1>❌ Erro</h1>

            <p>
            Não foi possível obter um Access Token válido.
            </p>
            """, 500

        api_response = requests.get(

            "https://api.mercadolibre.com/users/me",

            headers={
                "Authorization":
                    f"Bearer {access_token}"
            },

            timeout=30,
        )

        if api_response.status_code == 200:

            dados = api_response.json()

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

                <h1>🔥 TOMA DESCONTO!</h1>

                <h2>🟢 Mercado Livre conectado</h2>

                <p>✅ Access Token válido</p>

                <p>✅ Banco de dados funcionando</p>

                <p>✅ Renovação automática configurada</p>

                <hr>

                <p>
                    👤 Usuário:
                    <strong>
                        {dados.get("id")}
                    </strong>
                </p>

                <p>
                    🏪 Apelido:
                    <strong>
                        {dados.get("nickname")}
                    </strong>
                </p>

            </body>

            </html>
            """

        return f"""
        <h1>⚠️ Token inválido</h1>

        <p>
        Mercado Livre respondeu:
        </p>

        <pre>{api_response.text}</pre>
        """, 500

    except Exception as e:

        return f"""
        <h1>❌ Erro no sistema</h1>

        <pre>{str(e)}</pre>
        """, 500


# ============================================================
# INICIAR AUTORIZAÇÃO
# ============================================================

@app.route("/mercadolivre")
def mercadolivre():

    if not MELI_CLIENT_ID:

        return """
        <h1>❌ Erro</h1>
        <p>MELI_CLIENT_ID não configurado.</p>
        """, 500

    if not MELI_CLIENT_SECRET:

        return """
        <h1>❌ Erro</h1>
        <p>MELI_CLIENT_SECRET não configurado.</p>
        """, 500

    if not DATABASE_URL:

        return """
        <h1>❌ Erro</h1>
        <p>DATABASE_URL não configurada.</p>
        """, 500

    # Criar state

    state = secrets.token_urlsafe(32)

    # Criar verifier

    code_verifier = gerar_code_verifier()

    # Criar challenge

    code_challenge = gerar_code_challenge(
        code_verifier
    )

    # URL do Mercado Livre

    authorization_url = (

        "https://auth.mercadolivre.com.br/authorization"

        "?response_type=code"

        f"&client_id={MELI_CLIENT_ID}"

        f"&redirect_uri={REDIRECT_URI}"

        f"&state={state}"

        f"&code_challenge={code_challenge}"

        "&code_challenge_method=S256"
    )

    response = make_response(
        redirect(authorization_url)
    )

    # Guardar temporariamente no navegador

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
# CALLBACK
# ============================================================

@app.route("/callback")
def callback():

    error = request.args.get("error")

    if error:

        return f"""
        <h1>❌ Autorização não concluída</h1>

        <p>Erro:</p>

        <pre>{error}</pre>
        """, 400

    code = request.args.get("code")

    state_recebido = request.args.get("state")

    state_salvo = request.cookies.get(
        "oauth_state"
    )

    code_verifier = request.cookies.get(
        "oauth_code_verifier"
    )

    if not code:

        return """
        <h1>❌ Erro</h1>

        <p>
        Código de autorização não recebido.
        </p>
        """, 400

    if not state_recebido or not state_salvo:

        return """
        <h1>❌ Erro de segurança</h1>

        <p>
        State não encontrado.
        </p>

        <p>
        Comece novamente pelo botão
        Conectar Mercado Livre.
        </p>
        """, 400

    if not secrets.compare_digest(
        state_recebido,
        state_salvo
    ):

        return """
        <h1>❌ Erro de segurança</h1>

        <p>
        O state não corresponde à autorização.
        </p>
        """, 400

    if not code_verifier:

        return """
        <h1>❌ Erro de segurança</h1>

        <p>
        Code verifier não encontrado.
        </p>
        """, 400

    # ========================================================
    # TROCAR CODE POR TOKEN
    # ========================================================

    response = requests.post(

        TOKEN_URL,

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

    if response.status_code != 200:

        return f"""
        <h1>❌ Erro ao obter Access Token</h1>

        <p>
        Status:
        <strong>
        {response.status_code}
        </strong>
        </p>

        <pre>{response.text}</pre>
        """, 500

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

    if not access_token:

        return """
        <h1>❌ Access Token não recebido</h1>
        """, 500

    if not refresh_token:

        return """
        <h1>❌ Refresh Token não recebido</h1>
        """, 500

    # ========================================================
    # SALVAR NO POSTGRESQL
    # ========================================================

    try:

        salvar_tokens(

            user_id,

            access_token,

            refresh_token,

            expires_in
        )

    except Exception as e:

        return f"""
        <h1>❌ Erro ao salvar tokens</h1>

        <pre>{str(e)}</pre>
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

    if api_response.status_code == 200:

        resposta = make_response("""

        <!DOCTYPE html>

        <html>

        <head>
            <meta charset="UTF-8">

            <title>
                TOMA DESCONTO
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
                ✅ Tokens salvos no PostgreSQL
            </p>

            <p>
                ✅ API funcionando
            </p>

            <hr>

            <h3>
                🔄 Renovação automática ativada
            </h3>

            <p>
                O sistema poderá renovar o Access Token
                automaticamente.
            </p>

            <br>

            <a href="/status">

                🔎 Ver status da conexão

            </a>

        </body>

        </html>

        """)

        resposta.delete_cookie(
            "oauth_state"
        )

        resposta.delete_cookie(
            "oauth_code_verifier"
        )

        return resposta

    return f"""
    <h1>⚠️ Token salvo</h1>

    <p>
    Os tokens foram salvos,
    mas o teste da API falhou.
    </p>

    <pre>{api_response.text}</pre>
    """, 500


# ============================================================
# INICIALIZAÇÃO
# ============================================================

try:

    criar_tabela()

    print(
        "Banco de dados inicializado."
    )

except Exception as e:

    print(
        "Erro ao inicializar banco:",
        e
    )


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
