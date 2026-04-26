#!/bin/bash

# Acessa o diretório do projeto
cd "$(dirname "$0")"

# Verifica se o ambiente virtual existe
if [ ! -f ".venv/bin/activate" ]; then
    echo "Ambiente virtual não encontrado. Por favor, crie com: python3 -m venv .venv"
    exit 1
fi

# Ativa o ambiente virtual
source .venv/bin/activate

echo "🚀 Iniciando o Django Q2 em segundo plano..."
python manage.py qcluster &
QCLUSTER_PID=$!

echo "🌐 Iniciando o servidor Web..."
python run_server.py &
SERVER_PID=$!

# Função para capturar o Ctrl+C e desligar ambos com segurança
cleanup() {
    echo ""
    echo "🛑 Desligando serviços..."
    kill $QCLUSTER_PID 2>/dev/null
    kill $SERVER_PID 2>/dev/null
    wait $QCLUSTER_PID 2>/dev/null
    wait $SERVER_PID 2>/dev/null
    echo "✅ Sistema encerrado."
    exit 0
}

# Associa o sinal de interrupção (Ctrl+C) à função cleanup
trap cleanup SIGINT SIGTERM

wait
cleanup
