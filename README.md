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

## Interfaces do Compilador

O MiniPar 2026.2 mantém as interfaces do 2026.1 e acrescenta uma segunda interface web, didática:

| Interface | Como abrir | Público |
|---|---|---|
| Terminal | `python main.py` → opção 1, ou `python main.py arquivo.minipar` | desenvolvedor |
| IDE Web (2026.1) | `python main.py` → opção 2 → http://127.0.0.1:5000 | desenvolvedor |
| **Interface Didática (2026.2)** | `python main.py` → opção 2 → **http://127.0.0.1:5000/didatico** | alunos iniciantes |

A interface didática mostra cada fase da compilação em um botão, na ordem do pipeline:
**1 Tokens · 2 AST · 3 Semântica · 4 TAC · 5 C++ · 6 Compilar (baixar executável) · 7 Executar**.
Cada fase traz uma explicação curta do que o compilador faz nela; erros aparecem com fase, linha e
coluna e são destacados no editor. A AST é desenhada como árvore gráfica (D3.js): nós coloridos por
categoria, recolher/expandir com clique, zoom e arrastar, e clique no nó destaca a linha no código.
Links diretos: `/didatico?exemplo=teste6_quicksort_classes.minipar&fase=ast`.

A interface usa a API v2 (`/api/v2/...`, uma rota por fase), descrita em `api_v2.py`.

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

---

## Fork e Join (paralelismo real)

`fork` dispara uma chamada de função como **subtarefa independente**, alocada a um núcleo da CPU ou a outro computador; `join` faz a tarefa principal esperar e, como expressão, recolhe o valor retornado.

```minipar
fork t1 = avaliar("Professor", lote1) on core 0;                 # núcleo 0 desta máquina
fork t2 = avaliar("Monitor 1", lote2) on host "192.168.0.10":5400; # outro computador
fork t3 = gerar_fractal();                                        # núcleo escolhido pelo sistema
var r1 = join t1;      # espera t1 e recebe o retorno
join t2, t3;           # apenas espera
```

- Cada subtarefa recebe **cópias** dos argumentos (dados independentes, como processos).
- `nucleo()` informa em qual núcleo da CPU o código está executando.
- O compilador avisa quando a função disparada altera variáveis globais ou atributos de um objeto (estado compartilhado entre subtarefas).

### Execução em dois computadores (`on host`)

O **mesmo executável** roda nos dois computadores; no computador remoto ele é iniciado em modo trabalhador:

```bash
# 1. Compile o programa nos dois computadores
python main.py tests/recursos/recurso_fork_remoto.minipar

# 2. Computador remoto (ex.: IP 192.168.0.10): modo trabalhador
./output/recurso_fork_remoto --worker 5400

# 3. Computador principal: execução normal
./output/recurso_fork_remoto
```

Para testar em uma única máquina, use dois terminais e o endereço `"127.0.0.1"`. Em dois computadores, troque o endereço no programa pelo IP do computador remoto e libere a porta no firewall. Apenas funções do programa (não métodos) podem ser executadas remotamente, e os argumentos devem ser números, textos, lógicos ou listas deles.
