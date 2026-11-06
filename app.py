from flask import Flask, render_template, request, jsonify
import subprocess
import os
import sys
import glob

from test_orchestrator import (
    get_spec_summary,
    finalize_test_execution,
    check_active_session_for_new_terminal,
    join_session,
    get_terminal_id,
    create_session,
    clear_session,
    set_session_phase,
    append_session_log,
    record_execution_output,
    _load_session,
    _save_session,
)

app = Flask(__name__)

# API v2: uma rota por fase do compilador (interface web didatica)
from api_v2 import api_v2
app.register_blueprint(api_v2)

# Configuração de Diretórios
TESTS_DIR = 'tests'
OUTPUT_DIR = 'output'
TEMP_DIR = 'temp_code'

os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/tests', methods=['GET'])
def get_tests():
    # Retorna os testes ordenados alfabeticamente
    tests = [os.path.basename(f) for f in glob.glob(os.path.join(TESTS_DIR, '*.minipar'))]
    return jsonify({"tests": sorted(tests)})

@app.route('/api/get_test', methods=['POST'])
def get_test():
    filename = request.json.get('filename')
    filepath = os.path.join(TESTS_DIR, filename)
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return jsonify({"code": f.read()})
    return jsonify({"error": "Arquivo não encontrado"}), 404

@app.route('/api/test_spec', methods=['POST'])
def get_test_spec_api():
    """Requisitos detectados automaticamente pelo program_analyzer."""
    filename = request.json.get('filename')
    spec = get_spec_summary(filename)
    if spec:
        return jsonify(spec)
    return jsonify({"requires_input": False, "multi_computer": None})


@app.route('/api/session', methods=['GET'])
def get_session():
    action, session = check_active_session_for_new_terminal()
    if session:
        return jsonify({
            "active": session.get("status") not in ("completed", "cancelled"),
            "session": session,
            "terminal_id": get_terminal_id(),
            "needs_choice": action is not None,
        })
    return jsonify({"active": False, "terminal_id": get_terminal_id()})


@app.route('/api/session/join', methods=['POST'])
def session_join():
    _, session = check_active_session_for_new_terminal()
    if session:
        join_session(session)
        return jsonify({"success": True, "session": session})
    return jsonify({"success": False, "error": "Nenhuma sessão ativa"}), 404


@app.route('/api/session/create', methods=['POST'])
def session_create():
    filename = request.json.get('filename')
    path = os.path.join(TESTS_DIR, filename)
    if not os.path.exists(path):
        return jsonify({"success": False, "error": "Arquivo não encontrado"}), 404
    from program_analyzer import get_program_spec
    spec = get_program_spec(path)
    if not spec.get('multi_computer'):
        return jsonify({"success": False, "error": "Programa não requer multi-terminal"}), 400
    session = create_session(path, spec)
    return jsonify({"success": True, "session": session})


@app.route('/api/session/ready', methods=['POST'])
def session_ready():
    session = _load_session()
    if session:
        session["status"] = "running"
        _save_session(session)
        return jsonify({"success": True})
    return jsonify({"success": False}), 404


@app.route('/api/session/clear', methods=['POST'])
def session_clear():
    clear_session()
    return jsonify({"success": True})


@app.route('/api/compile', methods=['POST'])
def compile_code():
    data = request.json
    code = data.get('code')
    filename = data.get('filename', 'ide_temp.minipar')
    user_inputs = data.get('inputs', [])
    
    # Salva o código recebido da IDE em um arquivo temporário
    file_path = os.path.join(TEMP_DIR, filename)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(code)
        
    base_name = filename.replace('.minipar', '')
    stdin_lines = user_inputs  # valores coletados pela IDE para input() no .minipar
    
    try:
        set_session_phase("compiling", "Compilando código MiniPar...", percent=60)
        append_session_log("Compilação iniciada via IDE Web.")
        # ==========================================
        # 1. FASE DE COMPILAÇÃO (Gera TAC e C++)
        # ==========================================
        process = subprocess.run(
            [sys.executable, 'main.py', file_path], 
            capture_output=True, 
            text=True, 
            timeout=15
        )
        
        # Junta logs do sistema
        full_output = process.stdout
        if process.stderr:
            full_output += "\n" + process.stderr
            
        success = process.returncode == 0

        # ==========================================
        # 2. FASE DE EXECUÇÃO (Roda o Binário C++)
        # ==========================================
        if success:
            set_session_phase("compiling", "Compilação concluída.", percent=80)
            append_session_log("Compilação concluída — executando binário.")
            exe_ext = ".exe" if sys.platform == "win32" else ""
            exe_path = os.path.join(OUTPUT_DIR, f"{base_name}{exe_ext}")
            
            if os.path.exists(exe_path):
                full_output += f"\n--- Executando {base_name} ---\n"
                set_session_phase("executing", f"Executando {base_name}...", percent=90)
                try:
                    stdin_data = None
                    if stdin_lines:
                        stdin_data = "\n".join(stdin_lines) + "\n"
                    exe_proc = subprocess.run(
                        [os.path.abspath(exe_path)], 
                        input=stdin_data,
                        capture_output=True, 
                        text=True, 
                        timeout=30
                    )
                    full_output += exe_proc.stdout
                    if exe_proc.stderr:
                        full_output += "\n[ERRO NA EXECUÇÃO]:\n" + exe_proc.stderr
                    record_execution_output(exe_proc.stdout or "")
                except subprocess.TimeoutExpired:
                    full_output += "\n[ERRO] Tempo limite de execução excedido (O programa entrou em loop infinito ou aguarda entrada de dados do usuário?)."
                    success = False
                except Exception as e:
                    full_output += f"\n[ERRO] Falha ao executar binário: {e}"
                    success = False
                
                full_output += "\n" + "-" * 40

                if filename.endswith('.minipar'):
                    test_source = os.path.join(TESTS_DIR, filename)
                    if os.path.exists(test_source):
                        finalize_test_execution(test_source, full_output)
        
        # ==========================================
        # 3. COLETA DOS ARQUIVOS GERADOS
        # ==========================================
        cpp_file = os.path.join(OUTPUT_DIR, f"{base_name}.cpp")
        tac_file = os.path.join(OUTPUT_DIR, f"{base_name}.tac")
        
        cpp_code = ""
        tac_code = ""
        
        if os.path.exists(cpp_file):
            with open(cpp_file, 'r', encoding='utf-8') as f:
                cpp_code = f.read()
                
        if os.path.exists(tac_file):
             with open(tac_file, 'r', encoding='utf-8') as f:
                tac_code = f.read()
                
        # Retorna o resultado. Se der erro, colocamos o log completo em stderr para o JS puxar
        return jsonify({
            "stdout": full_output if success else "",
            "stderr": full_output if not success else "",
            "cpp": cpp_code,
            "tac": tac_code,
            "success": success
        })
        
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Tempo limite do compilador excedido.", "success": False}), 500
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500

if __name__ == '__main__':
    # Roda a IDE silenciosamente
    app.run(debug=False, port=5000)