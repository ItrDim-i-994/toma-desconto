import os
import secrets
import hashlib
import base64
import requests
import psycopg2

from flask import Flask, redirect, request, make_response

app = Flask(__name__)

# ============================================================
# CONFIGURAÃ‡Ã•ES
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
        raise Exception("DATABASE_URL nÃ£o configurada.")

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
            "ERRO: Mercado Livre nÃ£o enviou novo refresh token."
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
# OBTER ACCESS TOKEN VÃLIDO
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
            "Access Token prÃ³ximo do vencimento."
        )

        return renovar_access_token()

    return access_token


# ============================================================
# BUSCAR PRODUTOS NO MERCADO LIVRE
# ============================================================
def buscar_produtos_mercado_livre(query, limit=20):

    access_token = obter_access_token()

    if not access_token:
        raise Exception("NÃ£o foi possÃ­vel obter um Access Token vÃ¡lido.")

    url = "https://api.mercadolibre.com/sites/MLB/search"

    parametros = {
        "q": query,
        "limit": limit
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }

    resposta = requests.get(
        url,
        params=parametros,
        headers=headers,
        timeout=30
    )

    if resposta.status_code != 200:
        raise Exception(
            f"Erro na busca do Mercado Livre: "
            f"HTTP {resposta.status_code}\n"
            f"URL: {resposta.url}\n"
            f"Resposta: {resposta.text}\n"
            f"Headers: {dict(resposta.headers)}"
        )

    return resposta.json()
# ============================================================
# DIAGNÃ“STICO DA APLICAÃ‡ÃƒO MERCADO LIVRE
# ============================================================

@app.route("/diagnostico-app")
def diagnostico_app():

    try:

        access_token = obter_access_token()

        if not access_token:
            return """
            <h1>âŒ Access Token nÃ£o disponÃ­vel</h1>
            """, 500

        headers = {
            "Authorization": f"Bearer {access_token}"
        }

        # ====================================================
        # CONSULTAR APLICAÃ‡ÃƒO
        # ====================================================

        app_response = requests.get(

            "https://api.mercadolibre.com/applications/7411717385543362",

            headers=headers,

            timeout=30
        )

        # ====================================================
        # CONSULTAR GRANTS
        # ====================================================

        grants_response = requests.get(

            "https://api.mercadolibre.com/applications/7411717385543362/grants",

            headers=headers,

            timeout=30
        )

        return f"""
        <!DOCTYPE html>

        <html>

        <head>
            <meta charset="UTF-8">

            <title>
                DiagnÃ³stico TOMA DESCONTO
            </title>
        </head>

        <body style="
            font-family: Arial;
            background: #f5f5f5;
            padding: 30px;
        ">

            <h1>ðŸ”¥ TOMA DESCONTO!</h1>

            <h2>ðŸ”Ž DiagnÃ³stico da aplicaÃ§Ã£o</h2>

            <hr>

            <h3>ðŸ“± AplicaÃ§Ã£o</h3>

            <p>
                Status HTTP:
                <strong>
                    {app_response.status_code}
                </strong>
            </p>

            <pre style="
                background: white;
                padding: 20px;
                overflow-x: auto;
            ">{app_response.text}</pre>

            <hr>

            <h3>ðŸ” Grants / PermissÃµes</h3>

            <p>
                Status HTTP:
                <strong>
                    {grants_response.status_code}
                </strong>
            </p>

            <pre style="
                background: white;
                padding: 20px;
                overflow-x: auto;
            ">{grants_response.text}</pre>

        </body>

        </html>
        """

    except Exception as e:

        return f"""
        <h1>âŒ Erro no diagnÃ³stico</h1>

        <pre>{str(e)}</pre>
        """, 500
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

        <h1>ðŸ”¥ TOMA DESCONTO!</h1>

        <h2>ðŸ¤– Sistema de Ofertas</h2>

        <p>Servidor online.</p>

        <br>

        <a href="/mercadolivre">

            <button style="
                font-size: 20px;
                padding: 15px 30px;
                cursor: pointer;
            ">

                ðŸ›’ Conectar Mercado Livre

            </button>

        </a>

        <br><br>

        <a href="/status">

            <button style="
                font-size: 16px;
                padding: 10px 20px;
                cursor: pointer;
            ">

                ðŸ”Ž Ver status

            </button>

        </a>

    </body>

    </html>
    """

# ============================================================
# BUSCAR PRODUTOS
# ============================================================

@app.route("/teste-token")
def teste_token():
    try:
        access_token = obter_access_token()

        if not access_token:
            return "<h1>âŒ Access Token nÃ£o disponÃ­vel</h1>", 500

        headers = {
            "Authorization": f"Bearer {access_token}"
        }

        resposta = requests.get(
            "https://api.mercadolibre.com/users/me",
            headers=headers,
            timeout=30
        )

        return f"""
        <h1>ðŸ”Ž TESTE DO ACCESS TOKEN</h1>
        <h2>Status HTTP: {resposta.status_code}</h2>
        <pre>{resposta.text}</pre>
        """

    except Exception as e:
        return f"<h1>âŒ Erro</h1><pre>{str(e)}</pre>", 500
@app.route("/teste-busca")
def teste_busca():
    try:
        access_token = obter_access_token()

        if not access_token:
            return "<h1>âŒ Access Token nÃ£o disponÃ­vel</h1>", 500

        headers = {
            "Authorization": f"Bearer {access_token}"
        }

        resposta = requests.get(
            "https://api.mercadolibre.com/sites/MLB/search",
            params={
                "q": "air fryer",
                "limit": 5
            },
            headers=headers,
            timeout=30
        )

        return f"""
        <h1>ðŸ”Ž TESTE DE BUSCA</h1>

        <h2>Status HTTP: {resposta.status_code}</h2>

        <h3>Resposta do Mercado Livre:</h3>

        <pre>{resposta.text}</pre>
        """

    except Exception as e:
        return f"""
        <h1>âŒ Erro no teste</h1>
        <pre>{str(e)}</pre>
        """, 500
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

            <h1>ðŸ”¥ TOMA DESCONTO!</h1>

            <h2>ðŸ”Ž Busca de produtos</h2>

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

            <h1>ðŸ”¥ TOMA DESCONTO!</h1>

            <h2>ðŸ”Ž Resultado da busca</h2>

            <p>
                Produto pesquisado:
                <strong>{produto}</strong>
            </p>

            <p>
                AnÃºncios encontrados:
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
                "Sem tÃ­tulo"
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
                    ðŸ†” ID:
                    <strong>{item_id}</strong>
                </p>

                <p>
                    ðŸ’° PreÃ§o:
                    <strong>{moeda} {preco}</strong>
                </p>

                <p>
                    ðŸ”—
                    <a
                        href="{link}"
                        target="_blank"
                        rel="noopener noreferrer"
                    >
                        Ver anÃºncio
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

            <h1>âŒ Erro na busca</h1>

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
            <h1>âš ï¸ Mercado Livre nÃ£o conectado</h1>

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
            <h1>âŒ Erro</h1>

            <p>
            NÃ£o foi possÃ­vel obter um Access Token vÃ¡lido.
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

                <h1>ðŸ”¥ TOMA DESCONTO!</h1>

                <h2>ðŸŸ¢ Mercado Livre conectado</h2>

                <p>âœ… Access Token vÃ¡lido</p>

                <p>âœ… Banco de dados funcionando</p>

                <p>âœ… RenovaÃ§Ã£o automÃ¡tica configurada</p>

                <hr>

                <p>
                    ðŸ‘¤ UsuÃ¡rio:
                    <strong>
                        {dados.get("id")}
                    </strong>
                </p>

                <p>
                    ðŸª Apelido:
                    <strong>
                        {dados.get("nickname")}
                    </strong>
                </p>

            </body>

            </html>
            """

        return f"""
        <h1>âš ï¸ Token invÃ¡lido</h1>

        <p>
        Mercado Livre respondeu:
        </p>

        <pre>{api_response.text}</pre>
        """, 500

    except Exception as e:

        return f"""
        <h1>âŒ Erro no sistema</h1>

        <pre>{str(e)}</pre>
        """, 500


# ============================================================
# INICIAR AUTORIZAÃ‡ÃƒO
# ============================================================

@app.route("/mercadolivre")
def mercadolivre():

    if not MELI_CLIENT_ID:

        return """
        <h1>âŒ Erro</h1>
        <p>MELI_CLIENT_ID nÃ£o configurado.</p>
        """, 500

    if not MELI_CLIENT_SECRET:

        return """
        <h1>âŒ Erro</h1>
        <p>MELI_CLIENT_SECRET nÃ£o configurado.</p>
        """, 500

    if not DATABASE_URL:

        return """
        <h1>âŒ Erro</h1>
        <p>DATABASE_URL nÃ£o configurada.</p>
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
        <h1>âŒ AutorizaÃ§Ã£o nÃ£o concluÃ­da</h1>

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
        <h1>âŒ Erro</h1>

        <p>
        CÃ³digo de autorizaÃ§Ã£o nÃ£o recebido.
        </p>
        """, 400

    if not state_recebido or not state_salvo:

        return """
        <h1>âŒ Erro de seguranÃ§a</h1>

        <p>
        State nÃ£o encontrado.
        </p>

        <p>
        Comece novamente pelo botÃ£o
        Conectar Mercado Livre.
        </p>
        """, 400

    if not secrets.compare_digest(
        state_recebido,
        state_salvo
    ):

        return """
        <h1>âŒ Erro de seguranÃ§a</h1>

        <p>
        O state nÃ£o corresponde Ã  autorizaÃ§Ã£o.
        </p>
        """, 400

    if not code_verifier:

        return """
        <h1>âŒ Erro de seguranÃ§a</h1>

        <p>
        Code verifier nÃ£o encontrado.
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
        <h1>âŒ Erro ao obter Access Token</h1>

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
        <h1>âŒ Access Token nÃ£o recebido</h1>
        """, 500

    if not refresh_token:

        return """
        <h1>âŒ Refresh Token nÃ£o recebido</h1>
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
        <h1>âŒ Erro ao salvar tokens</h1>

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
                ðŸŽ‰ Mercado Livre conectado!
            </h1>

            <h2>
                ðŸ”¥ TOMA DESCONTO!
            </h2>

            <p>
                âœ… OAuth funcionando
            </p>

            <p>
                âœ… PKCE funcionando
            </p>

            <p>
                âœ… Access Token recebido
            </p>

            <p>
                âœ… Refresh Token recebido
            </p>

            <p>
                âœ… Tokens salvos no PostgreSQL
            </p>

            <p>
                âœ… API funcionando
            </p>

            <hr>

            <h3>
                ðŸ”„ RenovaÃ§Ã£o automÃ¡tica ativada
            </h3>

            <p>
                O sistema poderÃ¡ renovar o Access Token
                automaticamente.
            </p>

            <br>

            <a href="/status">

                ðŸ”Ž Ver status da conexÃ£o

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
    <h1>âš ï¸ Token salvo</h1>

    <p>
    Os tokens foram salvos,
    mas o teste da API falhou.
    </p>

    <pre>{api_response.text}</pre>
    """, 500


# ============================================================
# INICIALIZAÃ‡ÃƒO
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
# EXECUÃ‡ÃƒO
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
@app.route("/teste-endpoint")
def teste_endpoint():
    try:
        access_token = obter_access_token()

        if not access_token:
            return "<h1>Access Token nÃ£o disponÃ­vel</h1>", 500

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }

        usuario = requests.get(
            "https://api.mercadolibre.com/users/me",
            headers=headers,
            timeout=30
        )

        if usuario.status_code != 200:
            return f"""
            <h1>Falha no /users/me</h1>
            <h2>Status HTTP: {usuario.status_code}</h2>
            <pre>{usuario.text}</pre>
            """, 500

        user_id = usuario.json().get("id")

        url = f"https://api.mercadolibre.com/users/{user_id}/items/search"

        resposta = requests.get(
            url,
            headers=headers,
            params={"limit": 5},
            timeout=30
        )

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Teste de Endpoint</title>
        </head>
        <body style="font-family: Arial; padding: 30px;">

            <h1>TESTE DE OUTRO ENDPOINT</h1>

            <p>/users/me:
                <strong>{usuario.status_code}</strong>
            </p>

            <p>UsuÃ¡rio:
                <strong>{user_id}</strong>
            </p>

            <p>Status do novo endpoint:
                <strong>{resposta.status_code}</strong>
            </p>

            <h3>Resposta:</h3>

            <pre>{resposta.text}</pre>

        </body>
        </html>
        """

    except Exception as e:
        return f"""
        <h1>Erro no teste</h1>
        <pre>{str(e)}</pre>
        """, 500

@app.route("/teste-highlights")
def teste_highlights():
    try:
        access_token = obter_access_token()

        if not access_token:
            return "<h1>Access Token nÃ£o disponÃ­vel</h1>", 500

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }

        url = "https://api.mercadolibre.com/highlights/MLB/category/MLB432825"

        resposta = requests.get(
            url,
            headers=headers,
            timeout=30
        )

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Teste Highlights</title>
        </head>
        <body style="font-family: Arial; padding: 30px;">

            <h1>ðŸ”¥ TESTE DE PRODUTOS MAIS VENDIDOS</h1>

            <h2>Status HTTP: {resposta.status_code}</h2>

            <h3>Resposta do Mercado Livre:</h3>

            <pre>{resposta.text}</pre>

        </body>
        </html>
        """

    except Exception as e:
        return f"""
        <h1>Erro no teste</h1>
        <pre>{str(e)}</pre>
        """, 500

@app.route("/teste-produto")
def teste_produto():
    try:
        access_token = obter_access_token()

        if not access_token:
            return "<h1>Access Token nÃ£o disponÃ­vel</h1>", 500

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }

        item_id = "MLB74960151"

        resposta = requests.get(
            f"https://api.mercadolibre.com/items/{item_id}",
            headers=headers,
            timeout=30
        )

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Teste Produto</title>
        </head>
        <body style="font-family: Arial; padding: 30px;">

            <h1>ðŸ›’ TESTE DE PRODUTO</h1>

            <h2>Status HTTP: {resposta.status_code}</h2>

            <h3>ID:</h3>
            <p>{item_id}</p>

            <h3>Resposta do Mercado Livre:</h3>

            <pre>{resposta.text}</pre>

        </body>
        </html>
        """

    except Exception as e:
        return f"""
        <h1>Erro no teste</h1>
        <pre>{str(e)}</pre>
        """, 500

@app.route("/teste-product")
def teste_product():
    try:
        access_token = obter_access_token()

        if not access_token:
            return "<h1>Access Token nÃ£o disponÃ­vel</h1>", 500

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }

        product_id = "MLB74960151"

        resposta = requests.get(
            f"https://api.mercadolibre.com/products/{product_id}",
            headers=headers,
            timeout=30
        )

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Teste Product</title>
        </head>
        <body style="font-family: Arial; padding: 30px;">

            <h1>ðŸ›’ TESTE DE PRODUTO DE CATÃLOGO</h1>

            <h2>Status HTTP: {resposta.status_code}</h2>

            <h3>Product ID:</h3>
            <p>{product_id}</p>

            <h3>Resposta do Mercado Livre:</h3>

            <pre>{resposta.text}</pre>

        </body>
        </html>
        """

    except Exception as e:
        return f"""
        <h1>Erro no teste</h1>
        <pre>{str(e)}</pre>
        """, 500

@app.route("/teste-buscar-product")
def teste_buscar_product():
    try:
        access_token = obter_access_token()

        if not access_token:
            return "<h1>Access Token nÃ£o disponÃ­vel</h1>", 500

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }

        product_id = "MLB74960151"

        resposta = requests.get(
            "https://api.mercadolibre.com/products/search",
            headers=headers,
            params={
                "status": "active",
                "site_id": "MLB",
                "q": product_id
            },
            timeout=30
        )

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Buscar Product</title>
        </head>
        <body style="font-family: Arial; padding: 30px;">

            <h1>ðŸ”Ž BUSCA DO PRODUTO</h1>

            <h2>Status HTTP: {resposta.status_code}</h2>

            <h3>Product ID pesquisado:</h3>
            <p>{product_id}</p>

            <h3>Resposta do Mercado Livre:</h3>

            <pre>{resposta.text}</pre>

        </body>
        </html>
        """

    except Exception as e:
        return f"""
        <h1>Erro no teste</h1>
        <pre>{str(e)}</pre>
        """, 500

@app.route("/teste-user-product")
def teste_user_product():
    try:
        access_token = obter_access_token()

        if not access_token:
            return "<h1>Access Token não disponível</h1>", 500

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }

        # Busca produtos em destaque no Mercado Livre
        resposta_highlights = requests.get(
            "https://api.mercadolibre.com/highlights/MLB/category/MLB432825",
            headers=headers,
            timeout=30
        )

        if resposta_highlights.status_code != 200:
            return f"""
            <h1>Erro ao buscar highlights</h1>
            <h2>Status: {resposta_highlights.status_code}</h2>
            <pre>{resposta_highlights.text}</pre>
            """, resposta_highlights.status_code

        dados = resposta_highlights.json()

        # Procura automaticamente um resultado USER_PRODUCT
        user_product_id = None

        for resultado in dados.get("content", []):
            if resultado.get("type") == "USER_PRODUCT":
                user_product_id = resultado.get("id")
                break

        if not user_product_id:
            return """
            <h1>USER_PRODUCT não encontrado</h1>
            <p>O Mercado Livre não retornou nenhum USER_PRODUCT nesta categoria.</p>
            <pre>{}</pre>
            """.format(resposta_highlights.text), 404

        # Consulta o USER_PRODUCT real
        resposta_product = requests.get(
            f"https://api.mercadolibre.com/user-products/{user_product_id}",
            headers=headers,
            timeout=30
        )

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>User Product</title>
        </head>
        <body style="font-family: Arial; padding: 30px;">

            <h1>🔥 USER PRODUCT REAL</h1>

            <h2>Status Highlights: {resposta_highlights.status_code}</h2>

            <h3>ID encontrado automaticamente:</h3>
            <p><strong>{user_product_id}</strong></p>

            <h2>Status User Product: {resposta_product.status_code}</h2>

            <h3>Resposta do Mercado Livre:</h3>

            <pre>{resposta_product.text}</pre>

        </body>
        </html>
        """

    except Exception as e:
        return f"""
        <h1>Erro no teste</h1>
        <pre>{str(e)}</pre>
        """, 500
