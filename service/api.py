from flask import Flask, jsonify, request
import jwt
import os
from datetime import datetime, timedelta
from functools import wraps

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return jsonify(message="Token não fornecido"), 401
        
        parts = auth_header.split()
        if parts[0].lower() != "bearer" or len(parts) != 2:
            return jsonify(message="Cabeçalho de autorização mal formatado"), 401
        
        token = parts[1]
        
        try:
            decoded = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            # Você pode passar o usuário decodificado para a função da rota, se precisar
            request.user = decoded['user'] 
        except jwt.ExpiredSignatureError:
            return jsonify(message="Token expirado! Conecte novamente"), 401
        except jwt.InvalidTokenError:
            return jsonify(message="Tok1en inválido"), 401
        
        return f(*args, **kwargs)
    return decorated

SECRET_KEY = os.getenv("SECRET_KEY", "ADMIN")

app = Flask(__name__)

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify(message="Dados de Login não fornecidos"), 400  
    if "username" not in data or "password" not in data:
        return jsonify(message="Campos 'username' e 'password' são obrigatórios!"), 400
    if data["username"] == "admin" and data["password"] == "123":
        token = jwt.encode(
            {
                'user': data['username'],
                'exp': datetime.utcnow() + timedelta(minutes=30)
            },
            SECRET_KEY,
            algorithm='HS256'
        )
        return jsonify(token=token)
    return jsonify(message="Credenciais inválidas"), 401

@app.route('/protected', methods=['GET'])
@token_required
def protected():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify(message="Token não fornecido"), 401
    parts = auth_header.split()
    if parts[0].lower() != "bearer" or len(parts) != 2:
        return jsonify(message="Cabeçalho mal formatado"), 401
    token = parts[1]
    try:
        decoded = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return jsonify(message="Cliente Conectado", user=decoded['user'])
    except jwt.ExpiredSignatureError:
        return jsonify(message="Token expirado! Conecte novamente"), 401
    except jwt.InvalidTokenError:
        return jsonify(message="Token inválido"), 401

@app.route('/consultas', methods=['GET'])
@token_required
def get_consultas():
    data = {'query':'all'}
    return jsonify(data)

@app.route('/consultas/<int:id>', methods=['GET'])
@token_required

def get_consulta(id):
    datas = {'query':'all'}
    data = next((item for item in datas if item["id"] == id), None)
    if data:
        return jsonify(data)
    else:
        return jsonify({"error": "Data not found"}), 404

if __name__ == '__main__':
    app.run(debug=True)
