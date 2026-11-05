# Compilador MiniPar
Trabalho de Compiladores - UFAL 


Arquitetura orientada a objetos baseada na versão C++ original, agora expandida para incluir **Geração de Código Intermediário (TAC)** de 3 endereços e uma nova **IDE Web**, capaz de gerar, compilar e executar o código C++ produzido pelo compilador.
Desenvolvido por:

Emanuele Vitória de Jesus Lima - [Manu-Vii](https://github.com/Manu-Vii)

José Lucas de Oliveira Quintela - [lucasqtl](https://github.com/lucasqtl)

Luiz Miguel de Melo Bomfim - [luizwhirl](https://github.com/luizwhirl)

---

## Estrutura do Projeto

```text
minipar_python/
├── src/
│   ├── interfaces.py      # Interfaces dos componentes (classes abstratas I*)
│   ├── erros.py           # Erros por fase (léxico, sintático, semântico, geração)
│   ├── controle.py        # C_Controle: coordena as fases + ResultadoCompilacao
│   ├── lexer.py           # C_Lexico: Analisador Léxico
│   ├── parser.py          # C_Sintatico: Analisador Sintático
│   ├── ast_nodes.py       # Nós da AST (dataclasses)
│   ├── semantic.py        # C_Semantico: Analisador Semântico
│   ├── tabela_simbolos.py # C_TabelaSimbolos: Tabela de Símbolos (pilha de escopos)
│   ├── tac.py             # C_GeradorTAC: Gerador de Código Intermediário (TAC)
│   ├── codegen.py         # C_GeradorCpp: Gerador de Código C++
│   ├── compilador_gcc.py  # C_CompiladorGcc: compila o C++ gerado com g++ -O3
│   └── cpp_template.py    # Template base em C++ (threads, sockets, listas)
├── static/               # Arquivos estáticos da IDE Web (CSS, JS)
├── templates/            # Arquivos HTML da IDE Web
├── tests/                # Exemplos e testes .minipar
├── output/               # Arquivos gerados (.cpp, .tac e executáveis)
├── temp_code/            # Códigos temporários executados pela IDE
├── app.py                # Servidor Flask da Interface Web
├── main.py               # Ponto de entrada principal (CLI e Interativo)
├── menu.py               # Menu interativo para terminal
├── requirements.txt      # Dependências Python
└── README.md
```

---

## Requisitos

- Python 3.8 ou superior
- `g++` disponível no PATH (para compilar o código C++ gerado)
- Flask (para executar a IDE Web)

Instalação das dependências:

```bash
pip install -r requirements.txt
```

---

## Como Usar

O compilador oferece múltiplas formas de interação.

### 1. Menu Interativo (Terminal ou IDE Web)

Execute o programa sem argumentos:

```bash
python main.py
```

Opções disponíveis:

- **[1] Modo Terminal**: navegação pelos testes através de um menu textual.
- **[2] Modo Web Interface**: inicia o servidor Flask.

Após iniciar a interface web, acesse:

```text
http://127.0.0.1:5000
```

A IDE permite:

- Editar código MiniPar
- Compilar o programa
- Visualizar o código TAC gerado
- Visualizar o código C++ gerado
- Executar o programa e ver a saída

### 2. Execução Direta (CLI)

Para compilar um arquivo específico:

```bash
python main.py tests/teste3_neuronio.minipar
```

O nome do arquivo de saída é opcional. Por padrão, será utilizado o mesmo nome do arquivo `.minipar`.

Os arquivos gerados (`.cpp`, `.tac` e executáveis) serão armazenados na pasta `output/`.

---

## Fases do Compilador

| Fase | Interface | Componente | Entrada → Saída |
|------|-----------|------------|-----------------|
| 1 | `ILexico` | `C_Lexico` | código-fonte → tokens |
| 2 | `ISintatico` | `C_Sintatico` | tokens → AST |
| 3 | `ISemantico` | `C_Semantico` (usa `ITabelaSimbolos` / `C_TabelaSimbolos`) | AST → AST validada + tabela de símbolos |
| 4 | `IGeradorTAC` | `C_GeradorTAC` | AST → código de três endereços |
| 5 | `IGeradorCpp` | `C_GeradorCpp` | AST → código C++ |
| 6 | `ICompiladorCpp` | `C_CompiladorGcc` | código C++ → executável (`g++ -O3`) |

### Arquitetura em Componentes de Software

Cada componente é uma classe `C_*` que herda de uma interface `I*` (classe abstrata) e contém o algoritmo da sua fase. O componente `C_Controle` (interface `IControle`) executa as fases na ordem acima conversando com os demais **somente pelas interfaces**:

```python
icontrole: IControle = C_Controle()
resultado = icontrole.compilar(codigo_fonte, "programa")
```

O `ResultadoCompilacao` devolvido guarda o produto de cada fase (tokens, AST, tabela de símbolos, TAC, C++, executável) e os erros com fase, linha e coluna. Se uma fase falhar, as seguintes não executam, mas o que já foi produzido continua disponível.

Erros léxicos e sintáticos interrompem a compilação no primeiro erro; o analisador semântico reporta todos os erros encontrados de uma vez.

---

## Sintaxe MiniPar

Exemplo:

```minipar
seq {
    var x = 42;

    print("Valor:", x);

    par {
        print("Thread A");
        print("Thread B");
    }
}
```

### Comandos Disponíveis

| Sintaxe | Descrição |
|----------|------------|
| `seq { ... }` | Bloco sequencial |
| `par { ... }` | Bloco paralelo (cada instrução gera uma thread C++) |
| `var nome = expr;` | Declaração de variável |
| `nome = expr;` | Atribuição |
| `print(expr, ...);` | Impressão na saída padrão |
| `# comentário` | Comentário de linha |

---
