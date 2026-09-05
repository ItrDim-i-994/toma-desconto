from flask import Flask

app = Flask(__name__)


@app.route("/")
def home():
    return """
    <html>
        <head>
            <title>TOMA DESCONTO!</title>
        </head>
        <body>
            <h1>🔥 TOMA DESCONTO!</h1>
            <p>Servidor online.</p>
            <p>🤖 Sistema de ofertas em preparação.</p>
        </body>
    </html>
    """


@app.route("/callback")
def callback():
    return """
    <html>
        <head>
            <title>TOMA DESCONTO - Autorização</title>
        </head>
        <body>
            <h1>🔥 TOMA DESCONTO!</h1>
            <p>Autorização recebida.</p>
            <p>Você pode fechar esta página.</p>
        </body>
    </html>
    """


if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
