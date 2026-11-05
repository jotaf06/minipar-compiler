import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, 'src'))

from lexer import Lexer
from parser import Parser
from semantic import SemanticAnalyzer
from tac import TACGenerator
from codegen import CppCodeGenerator
from erros import ErroLexico, ErroSintatico

def compile_file(source_path: str, output_name: str) -> bool:
    """Processa as 3 Fases do Compilador em um arquivo alvo."""
    print(f"\n=== Compilando: {source_path} ===")
    try:
        with open(source_path, encoding="utf-8") as f:
            source_code = f.read()
    except FileNotFoundError:
        print(f"[ERRO] Arquivo nao encontrado: {source_path}", file=sys.stderr)
        return False

    try:
        print("[Fase 1] Analise Lexica e Sintatica...")
        lexer  = Lexer(source_code)
        tokens = lexer.tokenize()

        parser  = Parser(tokens)
        program = parser.parse()
    except (ErroLexico, ErroSintatico) as erro:
        # Lexico/sintatico: param no primeiro erro (nao ha AST confiavel para continuar)
        print(erro, file=sys.stderr)
        print("[ERRO] Compilacao abortada.", file=sys.stderr)
        return False

    print("[Fase 2] Analise Semantica e Tabela de Simbolos...")
    semantic = SemanticAnalyzer()
    if not semantic.analyze(program):
        # Semantico: todos os erros encontrados sao exibidos de uma vez
        for erro in semantic.erros:
            print(erro, file=sys.stderr)
        print(f"[ERRO] Falha na Analise Semantica ({len(semantic.erros)} erro(s)). Compilacao abortada.", file=sys.stderr)
        return False

    print("[Fase 3] Geracao de Codigo Intermediario (TAC - 3 enderecos)...")
    tac = TACGenerator()
    tac_path = tac.generate(program, output_name)
    print(f"[TAC] Arquivo gerado: {tac_path}")

    print("[Fase 4] Transpilacao e Chamada do GCC (-O3)...")
    codegen = CppCodeGenerator()
    return codegen.generate(program, output_name)


def start_interactive():
    """Inicia a tela de seleção inicial do sistema."""
    from test_orchestrator import (
        check_active_session_for_new_terminal,
        join_session,
        get_terminal_id,
        run_joiner_progress_monitor,
        _load_session,
    )

    # Segundo terminal detectou sessão ativa — entra como participante antes do menu
    action, session = check_active_session_for_new_terminal()
    if action == "join" and session:
        join_session(session)
        session = _load_session() or session
        print("\n" + "=" * 45)
        print("  MINIPAR — PARTICIPANTE DE TESTE")
        print("=" * 45)
        print(f"\n  Terminal identificado: {get_terminal_id()}")
        print(f"  Teste em andamento: {session.get('titulo', session.get('test_file', ''))}")
        print("\n  Monitor de progresso iniciado...\n")
        run_joiner_progress_monitor(session)
    elif action == "independent":
        print("\n  [INFO] Sessão em andamento ignorada — modo independente.\n")

    print("\n" + "=" * 45)
    print("      MINIPAR COMPILER & IDE")
    print("=" * 45)
    print("\nComo você deseja rodar o sistema?\n")
    print("[1] - Modo Terminal (Menu Interativo)")
    print("[2] - Modo Web Interface (IDE no Navegador)\n")
    
    escolha = input("Digite a sua escolha (1 ou 2): ").strip()
    
    if escolha == '1':
        print("\nIniciando modo Terminal...\n")
        try:
            import menu
            menu.exibir_menu()
        except ImportError as e:
            print(f"[ERRO] Falha ao carregar o menu: {e}")
            
    elif escolha == '2':
        print("\nIniciando Web Interface IDE...")
        print("Servidor inicializado! Acesse no navegador: http://127.0.0.1:5000\n")
        try:
            from app import app
            # Executa o Flask. Deixamos debug=False para o terminal ficar mais limpo
            app.run(host="127.0.0.1", port=5000, debug=False)
        except ImportError as e:
            print(f"[ERRO] Falha ao carregar a interface web: {e}")
        except Exception as e:
            print(f"[ERRO] Erro ao iniciar o servidor Flask: {e}")
    else:
        print("\n[ERRO] Escolha inválida. Finalizando o sistema.")


def main() -> int:
    # Se rodar sem argumentos (ex: `python main.py`), inicia a interface de escolha
    if len(sys.argv) < 2:
        start_interactive()
        return 0

    # Caso o script seja chamado via subprocesso pela IDE (passando arquivo como argumento)
    source_path  = sys.argv[1]
    
    # Se não passarem o nome da saída manualmente, extraímos do nome do próprio arquivo Minipar
    if len(sys.argv) > 2:
        output_name = sys.argv[2]
    else:
        base_file = os.path.basename(source_path)
        output_name = base_file.replace('.minipar', '')

    print("=== Compilador MiniPar ===")
    success = compile_file(source_path, output_name)
    
    if success:
        print("=== Processo Finalizado ===")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())