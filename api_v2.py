"""
API v2 do Compilador MiniPar 2026.2 - uma rota por fase do compilador.

Usada pela interface web didatica (cada botao chama uma fase). Diferente da API
antiga (/api/compile, mantida para a IDE do desenvolvedor), as fases de analise
usam o componente C_Controle diretamente, sem subprocesso.

Rotas (todas recebem JSON {"codigo": "..."}; respostas em JSON):

    POST /api/v2/analisar     todas as fases ate o C++ (sem compilar com g++)
    POST /api/v2/tokens       fase 1 - lista de tokens
    POST /api/v2/ast          fase 2 - arvore sintatica
    POST /api/v2/semantico    fase 3 - erros, avisos e tabela de simbolos
    POST /api/v2/tac          fase 4 - codigo de tres enderecos
    POST /api/v2/cpp          fase 5 - codigo C++ gerado
    POST /api/v2/compilar     fase 6 - gera o executavel; devolve o id para download
    GET  /api/v2/download/<id>         baixa o executavel compilado
    POST /api/v2/executar     compila e executa ({"codigo", "entradas": [...]})

Toda resposta traz "sucesso", "fase_erro" e "erros" (com fase, linha e coluna) e o
que as fases anteriores produziram, para a interface marcar o erro no editor.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
import uuid

from flask import Blueprint, jsonify, request, send_file

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, "src"))

from controle import C_Controle, ResultadoCompilacao   # noqa: E402
from ast_json import ast_para_dict                      # noqa: E402
from compilador_gcc import EXE_EXT                       # noqa: E402

api_v2 = Blueprint("api_v2", __name__, url_prefix="/api/v2")

PASTA_WEB = os.path.join(BASE_DIR, "output", "web")   # um subdiretorio por compilacao
TEMPO_MAX_EXECUCAO = 30                                # segundos
IDADE_MAX_COMPILACAO = 3600                            # compilacoes antigas sao apagadas
TAMANHO_MAX_CODIGO = 200_000                           # caracteres
LIMITE_SAIDA = 100_000                                 # bytes de saida guardados por execucao


class RequisicaoInvalida(Exception):
    pass


def _ler_codigo() -> str:
    dados = request.get_json(silent=True) or {}
    codigo = dados.get("codigo")
    if not isinstance(codigo, str):
        raise RequisicaoInvalida("Envie o codigo MiniPar no campo 'codigo'.")
    if len(codigo) > TAMANHO_MAX_CODIGO:
        raise RequisicaoInvalida("Codigo muito grande.")
    return codigo


def _limpar_compilacoes_antigas() -> None:
    if not os.path.isdir(PASTA_WEB):
        return
    agora = time.time()
    for nome in os.listdir(PASTA_WEB):
        caminho = os.path.join(PASTA_WEB, nome)
        if os.path.isdir(caminho) and agora - os.path.getmtime(caminho) > IDADE_MAX_COMPILACAO:
            shutil.rmtree(caminho, ignore_errors=True)


def _compilar(codigo: str, gerar_executavel: bool):
    """Compila em um diretorio proprio. Um C_Controle novo por requisicao: os
    componentes guardam estado e o Flask atende requisicoes em paralelo."""
    id_compilacao = uuid.uuid4().hex[:12]
    pasta = os.path.join(PASTA_WEB, id_compilacao)
    os.makedirs(pasta, exist_ok=True)
    resultado = C_Controle(pasta_saida=pasta).compilar(codigo, "programa", gerar_executavel)
    return id_compilacao, resultado


def _base(r: ResultadoCompilacao) -> dict:
    d = r.para_dict()
    return {
        "sucesso": d["sucesso"],
        "fase_erro": d["fase_erro"],
        "erros": d["erros"],
        "avisos": d["avisos"],
    }


def _resposta_fase(campos):
    """Executa as fases de analise e devolve os campos pedidos."""
    try:
        codigo = _ler_codigo()
        id_compilacao, r = _compilar(codigo, gerar_executavel=False)
        # A analise nao gera executavel: os arquivos .tac/.cpp intermediarios sao descartados
        shutil.rmtree(os.path.join(PASTA_WEB, id_compilacao), ignore_errors=True)
        d = r.para_dict()
        resposta = _base(r)
        for campo in campos:
            if campo == "ast":
                resposta["ast"] = ast_para_dict(r.ast)
            else:
                resposta[campo] = d[campo]
        return jsonify(resposta)
    except RequisicaoInvalida as e:
        return jsonify({"sucesso": False, "erro_interno": str(e)}), 400
    except Exception as e:   # erro inesperado do compilador: nao derruba o servidor
        return jsonify({"sucesso": False, "erro_interno": f"{type(e).__name__}: {e}"}), 500


def _executar_limitado(executavel: str, stdin: str) -> dict:
    """Executa o programa com limite de tempo e de saida: um laco que imprime sem parar
    nao pode acumular gigabytes na memoria do servidor."""
    proc = subprocess.Popen([executavel], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, cwd=os.path.dirname(executavel))
    saidas = {"stdout": bytearray(), "stderr": bytearray()}
    excedeu = threading.Event()

    def ler(fluxo, destino):
        for bloco in iter(lambda: fluxo.read(4096), b""):
            if len(destino) < LIMITE_SAIDA:
                destino.extend(bloco[: LIMITE_SAIDA - len(destino)])
            else:
                excedeu.set()
                proc.kill()       # saida demais: encerra o programa
                break

    leitores = [threading.Thread(target=ler, args=(proc.stdout, saidas["stdout"])),
                threading.Thread(target=ler, args=(proc.stderr, saidas["stderr"]))]
    for t in leitores: t.start()
    try:
        proc.stdin.write(stdin.encode("utf-8"))
        proc.stdin.close()
    except BrokenPipeError:
        pass                      # o programa terminou sem ler a entrada
    tempo_limite = False
    try:
        proc.wait(timeout=TEMPO_MAX_EXECUCAO)
    except subprocess.TimeoutExpired:
        tempo_limite = True
        proc.kill()
        proc.wait()
    for t in leitores: t.join()

    def texto(dados: bytearray) -> str:
        return dados.decode("utf-8", errors="replace")   # saida invalida nao derruba a rota

    return {
        "saida": texto(saidas["stdout"]),
        "erros_execucao": texto(saidas["stderr"]),
        "codigo_saida": None if (tempo_limite or excedeu.is_set()) else proc.returncode,
        "tempo_limite": tempo_limite,
        "saida_truncada": excedeu.is_set(),
    }


@api_v2.route("/analisar", methods=["POST"])
def analisar():
    return _resposta_fase(["tokens", "ast", "simbolos", "tac", "cpp"])


@api_v2.route("/tokens", methods=["POST"])
def tokens():
    return _resposta_fase(["tokens"])


@api_v2.route("/ast", methods=["POST"])
def ast():
    return _resposta_fase(["ast"])


@api_v2.route("/semantico", methods=["POST"])
def semantico():
    return _resposta_fase(["simbolos"])


@api_v2.route("/tac", methods=["POST"])
def tac():
    return _resposta_fase(["tac"])


@api_v2.route("/cpp", methods=["POST"])
def cpp():
    return _resposta_fase(["cpp"])


@api_v2.route("/compilar", methods=["POST"])
def compilar():
    try:
        _limpar_compilacoes_antigas()
        codigo = _ler_codigo()
        id_compilacao, r = _compilar(codigo, gerar_executavel=True)
        resposta = _base(r)
        if r.sucesso:
            resposta["id"] = id_compilacao
            resposta["download"] = f"/api/v2/download/{id_compilacao}"
        return jsonify(resposta)
    except RequisicaoInvalida as e:
        return jsonify({"sucesso": False, "erro_interno": str(e)}), 400
    except Exception as e:
        return jsonify({"sucesso": False, "erro_interno": f"{type(e).__name__}: {e}"}), 500


@api_v2.route("/download/<id_compilacao>", methods=["GET"])
def download(id_compilacao):
    if not id_compilacao.isalnum():                       # impede caminhos como ../
        return jsonify({"erro_interno": "id invalido"}), 400
    caminho = os.path.join(PASTA_WEB, id_compilacao, f"programa{EXE_EXT}")
    if not os.path.isfile(caminho):
        return jsonify({"erro_interno": "Executavel nao encontrado (compile novamente)."}), 404
    return send_file(caminho, as_attachment=True, download_name=f"programa_minipar{EXE_EXT}")


@api_v2.route("/executar", methods=["POST"])
def executar():
    try:
        _limpar_compilacoes_antigas()
        codigo = _ler_codigo()
        entradas = (request.get_json(silent=True) or {}).get("entradas") or []
        if not isinstance(entradas, list):
            raise RequisicaoInvalida("'entradas' deve ser uma lista (uma linha por input()).")
        id_compilacao, r = _compilar(codigo, gerar_executavel=True)
        resposta = _base(r)
        if not r.sucesso:
            return jsonify(resposta)
        stdin = "\n".join(str(e) for e in entradas) + ("\n" if entradas else "")
        inicio = time.time()
        resposta.update(_executar_limitado(os.path.abspath(r.executavel), stdin))
        resposta["tempo_execucao"] = round(time.time() - inicio, 3)
        resposta["id"] = id_compilacao
        return jsonify(resposta)
    except RequisicaoInvalida as e:
        return jsonify({"sucesso": False, "erro_interno": str(e)}), 400
    except Exception as e:
        return jsonify({"sucesso": False, "erro_interno": f"{type(e).__name__}: {e}"}), 500
