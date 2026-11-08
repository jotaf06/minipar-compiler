#!/usr/bin/env bash
# Executa todos os testes automatizados do MiniPar 2026.2 e gera
# tests/resultados/RESULTADOS.md (tabela para o relatorio).
#
#   ./run_tests.sh            todos os testes (unidade, API e integracao com g++)
#   ./run_tests.sh --rapido   so os testes de unidade e do C_Controle (segundos)
#   ./run_tests.sh -q         sem listar cada teste
set -euo pipefail
cd "$(dirname "$0")"

if [ -x .venv/bin/python ]; then
    PYTHON=.venv/bin/python
else
    PYTHON=python3
fi

# Flask so e necessario para os testes da API (pulados com --rapido)
if [[ " $* " != *" --rapido "* ]] && ! "$PYTHON" -c "import flask" 2>/dev/null; then
    echo "[ERRO] Flask nao encontrado. Crie o ambiente virtual:" >&2
    echo "  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
    exit 2
fi

exec "$PYTHON" tests/executar_testes.py "$@"
