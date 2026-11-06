/*
 * Interface didatica do MiniPar 2026.2.
 * Cada botao mostra uma fase do compilador, usando a API v2 (/api/v2/...).
 * As fases 1 a 5 vem de uma unica analise (/api/v2/analisar), refeita apenas
 * quando o codigo muda; compilar e executar chamam suas proprias rotas.
 */
(function () {
    "use strict";

    // ------------------------------------------------------------------
    // Fases da compilacao (ordem do pipeline) e o que cada uma faz
    // ------------------------------------------------------------------
    const FASES = [
        { id: "tokens", num: 1, nome: "Tokens", sub: "Análise léxica",
          desc: "O analisador léxico lê o código caractere por caractere e o agrupa em tokens: palavras reservadas, nomes, números, textos e símbolos. Espaços e comentários (#) são descartados. Passe o mouse sobre um token para vê-lo no código." },
        { id: "ast", num: 2, nome: "AST", sub: "Análise sintática",
          desc: "O analisador sintático confere se os tokens seguem a gramática (BNF) e monta a Árvore Sintática Abstrata, a estrutura do programa. Clique em um nó para recolher ou expandir seus filhos; a linha correspondente é destacada no editor. Use a roda do mouse para zoom e arraste para mover." },
        { id: "semantico", num: 3, nome: "Semântica", sub: "Análise semântica",
          desc: "O analisador semântico confere o significado do programa: variáveis declaradas antes do uso, tipos compatíveis, número de argumentos e as regras de fork/join. Os nomes declarados formam a tabela de símbolos, organizada por escopo." },
        { id: "tac", num: 4, nome: "TAC", sub: "Código de 3 endereços",
          desc: "O código intermediário quebra cada expressão em instruções simples, com no máximo três endereços (ex.: t1 = a + b), usando temporários t0, t1... Decisões e laços viram rótulos e desvios (ifFalse ... goto)." },
        { id: "cpp", num: 5, nome: "C++", sub: "Código gerado",
          desc: "O gerador traduz a AST para C++20: classes MiniPar viram classes C++, blocos par e fork viram threads, e canais viram sockets TCP. É esse código que o g++ compila." },
        { id: "compilar", num: 6, nome: "Compilar", sub: "Executável",
          desc: "O g++ compila o C++ gerado com otimização (-O3) e produz um executável nativo, que pode ser baixado e executado fora do navegador." },
        { id: "executar", num: 7, nome: "Executar", sub: "Saída do programa",
          desc: "O executável roda no servidor e a saída aparece abaixo. Se o programa usa input(), escreva os valores no campo de entradas, um por linha." },
    ];
    // Fase em que a compilacao parou -> botao correspondente
    const FASE_DO_ERRO = { LEXICO: "tokens", SINTATICO: "ast", SEMANTICO: "semantico", TAC: "tac", CPP: "cpp", GCC: "compilar" };

    const CORES_CATEGORIA = {
        declaracao: { fundo: "#f3eefe", borda: "#7c3aed", nome: "declaração" },
        comando:    { fundo: "#eaf1fe", borda: "#2563eb", nome: "comando" },
        bloco:      { fundo: "#f1f4f8", borda: "#64748b", nome: "bloco" },
        expressao:  { fundo: "#e6f6f4", borda: "#0d9488", nome: "expressão" },
        paralelo:   { fundo: "#fdf0e6", borda: "#ea580c", nome: "paralelismo" },
    };

    // Categorias dos tokens (para cor e resumo)
    const RESERVADAS = new Set(["CLASS", "EXTENDS", "NEW", "FUNC", "VAR", "IF", "ELSE", "WHILE", "DO", "FOR", "IN",
        "BREAK", "CONTINUE", "RETURN", "SEQ", "PAR", "THIS", "C_CHANNEL", "SEND", "RECEIVE", "INPUT", "PRINT",
        "MATRIX", "FORK", "JOIN", "ON", "CORE", "HOST", "TYPE"]);
    const DELIMITADORES = new Set(["LPAREN", "RPAREN", "LBRACE", "RBRACE", "LBRACKET", "RBRACKET", "SEMICOLON", "COMMA", "DOT", "COLON"]);
    const CATEGORIAS_TOKEN = {
        reservada:     { cor: "#7c3aed", nome: "palavra reservada" },
        identificador: { cor: "#0f766e", nome: "identificador" },
        numero:        { cor: "#b45309", nome: "número" },
        texto:         { cor: "#15803d", nome: "texto" },
        logico:        { cor: "#be185d", nome: "lógico" },
        operador:      { cor: "#2563eb", nome: "operador" },
        delimitador:   { cor: "#64748b", nome: "delimitador" },
    };
    function categoriaToken(tipo) {
        if (RESERVADAS.has(tipo)) return "reservada";
        if (tipo === "IDENTIFIER") return "identificador";
        if (tipo === "NUMBER") return "numero";
        if (tipo === "STRING_LITERAL") return "texto";
        if (tipo === "BOOL_LITERAL") return "logico";
        if (DELIMITADORES.has(tipo)) return "delimitador";
        return "operador";
    }

    const NOMES_TIPO = { FUNC: "função", CLASS: "classe", tarefa: "tarefa (fork)", number: "número", int: "inteiro",
        string: "texto", list: "lista", bool: "lógico", matrix: "matriz", var: "valor", c_channel: "canal", unknown: "?" };

    // ------------------------------------------------------------------
    // Estado
    // ------------------------------------------------------------------
    let editor;                 // CodeMirror do codigo MiniPar
    let analise = null;         // ultima resposta de /api/v2/analisar
    let codigoAnalisado = null; // codigo correspondente a 'analise'
    let faseAtual = null;
    let destaques = [];         // marcas no editor (linhas e tokens)
    let cppEditor = null;

    const $ = (id) => document.getElementById(id);
    const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

    // ------------------------------------------------------------------
    // Editor com destaque de sintaxe do MiniPar
    // ------------------------------------------------------------------
    CodeMirror.defineSimpleMode("minipar", {
        start: [
            { regex: /#.*/, token: "comment" },
            { regex: /"(?:[^\\"]|\\.)*"?/, token: "string" },
            { regex: /\b(?:fork|join|on|core|host|par|seq|c_channel|send|receive)\b/, token: "minipar-paralelo" },
            { regex: /\b(?:class|extends|new|func|var|if|else|while|do|for|in|break|continue|return|this|input|print|matrix)\b/, token: "keyword" },
            { regex: /\b(?:number|int|string|bool|void|list|dict)\b/, token: "type" },
            { regex: /\b(?:true|false)\b/, token: "atom" },
            { regex: /0x[0-9a-fA-F]+|\d+(?:\.\d+)?/, token: "number" },
            { regex: /[-+*\/%=<>!&|^]+/, token: "operator" },
        ],
    });

    function iniciarEditor() {
        editor = CodeMirror.fromTextArea($("editor"), {
            mode: "minipar", lineNumbers: true, indentUnit: 4, tabSize: 4, matchBrackets: true,
        });
        editor.on("change", () => {
            $("status-editor").textContent = "editado";
            $("status-editor").classList.remove("analisado");
            limparDestaques();
        });
    }

    function limparDestaques() {
        destaques.forEach((d) => (d.clear ? d.clear() : editor.removeLineClass(d, "background")));
        destaques = [];
    }

    function destacarLinha(linha, classe = "linha-destaque", rolar = true) {
        if (!linha) return;
        const h = editor.addLineClass(linha - 1, "background", classe);
        destaques.push(h);
        if (rolar) editor.scrollIntoView({ line: linha - 1, ch: 0 }, 80);
    }

    function selecionarLinha(linha) {
        limparDestaques();
        marcarErrosNoEditor();
        destacarLinha(linha);
    }

    // ------------------------------------------------------------------
    // Pipeline (botoes) e explicacao
    // ------------------------------------------------------------------
    function montarPipeline() {
        const nav = $("pipeline");
        FASES.forEach((f) => {
            const b = document.createElement("button");
            b.className = "fase";
            b.id = "fase-" + f.id;
            b.innerHTML = `<span class="estado"></span><span class="num">${f.num}</span>
                           <span class="nome">${f.nome}</span><span class="sub">${f.sub}</span>`;
            b.addEventListener("click", () => abrirFase(f.id));
            nav.appendChild(b);
        });
    }

    function atualizarEstados() {
        FASES.forEach((f) => $("fase-" + f.id).classList.remove("ok", "erro", "aviso", "bloqueada"));
        if (!analise) return;
        const faseErro = FASE_DO_ERRO[analise.fase_erro];
        let depoisDoErro = false;
        for (const f of FASES.slice(0, 5)) {
            const b = $("fase-" + f.id);
            if (f.id === faseErro) { b.classList.add("erro"); depoisDoErro = true; }
            else if (depoisDoErro) b.classList.add("bloqueada");
            else b.classList.add(f.id === "semantico" && analise.avisos.length ? "aviso" : "ok");
        }
        if (faseErro) ["compilar", "executar"].forEach((id) => $("fase-" + id).classList.add("bloqueada"));
    }

    function mostrarExplicacao(fase) {
        $("explicacao-titulo").textContent = `${fase.num} · ${fase.nome} — ${fase.sub}`;
        $("explicacao-texto").textContent = fase.desc;
    }

    // ------------------------------------------------------------------
    // Erros e avisos (painel + editor)
    // ------------------------------------------------------------------
    function marcarErrosNoEditor() {
        if (!analise) return;
        analise.erros.forEach((e) => destacarLinha(e.linha, "linha-erro", false));
    }

    function mostrarMensagens(erros, avisos) {
        const caixa = $("erros");
        const itens = [
            ...erros.map((e) => ({ ...e, classe: "erro", titulo: "Erro " + (e.fase || "").toLowerCase() })),
            ...(avisos || []).map((a) => ({ ...a, classe: "aviso", titulo: "Aviso" })),
        ];
        caixa.hidden = itens.length === 0;
        caixa.innerHTML = "";
        itens.forEach((m) => {
            const div = document.createElement("div");
            div.className = "msg " + m.classe;
            const onde = m.linha ? `linha ${m.linha}${m.coluna ? ", col. " + m.coluna : ""}` : "";
            div.innerHTML = `<span class="onde">${esc(m.titulo)}${onde ? " · " + onde : ""}</span>
                             <span>${esc(m.mensagem)}</span>`;
            if (m.linha) div.addEventListener("click", () => selecionarLinha(m.linha));
            caixa.appendChild(div);
        });
    }

    // ------------------------------------------------------------------
    // Comunicacao com a API v2
    // ------------------------------------------------------------------
    async function postar(rota, corpo) {
        const r = await fetch("/api/v2/" + rota, {
            method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo),
        });
        const d = await r.json();
        if (d.erro_interno) throw new Error(d.erro_interno);
        return d;
    }

    async function garantirAnalise() {
        const codigo = editor.getValue();
        if (analise && codigo === codigoAnalisado) return analise;
        analise = await postar("analisar", { codigo });
        codigoAnalisado = codigo;
        $("status-editor").textContent = analise.sucesso ? "analisado ✓" : "analisado com erros";
        $("status-editor").classList.toggle("analisado", analise.sucesso);
        atualizarEstados();
        return analise;
    }

    // ------------------------------------------------------------------
    // Abrir uma fase
    // ------------------------------------------------------------------
    async function abrirFase(id) {
        const fase = FASES.find((f) => f.id === id);
        faseAtual = id;
        document.querySelectorAll(".fase").forEach((b) => b.classList.toggle("ativa", b.id === "fase-" + id));
        mostrarExplicacao(fase);
        const botao = $("fase-" + id);
        botao.classList.add("carregando");
        try {
            const a = await garantirAnalise();
            limparDestaques();
            marcarErrosNoEditor();
            mostrarMensagens(a.erros, a.avisos);
            const conteudo = $("conteudo");
            conteudo.innerHTML = "";
            conteudo.scrollTop = 0;
            ({ tokens: renderTokens, ast: renderAst, semantico: renderSemantico, tac: renderTac,
               cpp: renderCpp, compilar: renderCompilar, executar: renderExecutar })[id](conteudo, a);
        } catch (e) {
            $("conteudo").innerHTML = `<div class="cartao"><b>Não foi possível falar com o servidor.</b>
                <p class="nota">${esc(e.message)}</p></div>`;
        } finally {
            botao.classList.remove("carregando");
        }
    }

    function faseIndisponivel(conteudo, a, oQue) {
        const fase = FASES.find((f) => f.id === FASE_DO_ERRO[a.fase_erro]);
        conteudo.innerHTML = `<div class="vazio"><p>${oQue} não foi gerado porque a compilação parou na fase
            <b>${fase ? fase.num + " · " + fase.nome : a.fase_erro}</b>.<br>Corrija o erro indicado acima.</p></div>`;
    }

    // ------------------------------------------------------------------
    // Dica flutuante
    // ------------------------------------------------------------------
    function mostrarDica(evento, html) {
        const d = $("dica");
        d.innerHTML = html;
        d.hidden = false;
        const x = Math.min(evento.clientX + 14, window.innerWidth - d.offsetWidth - 8);
        const y = Math.min(evento.clientY + 14, window.innerHeight - d.offsetHeight - 8);
        d.style.left = x + "px";
        d.style.top = y + "px";
    }
    const esconderDica = () => ($("dica").hidden = true);

    // ------------------------------------------------------------------
    // Fase 1: Tokens (agrupados por linha do codigo)
    // ------------------------------------------------------------------
    function renderTokens(conteudo, a) {
        const tokens = (a.tokens || []).filter((t) => t.tipo !== "END_OF_FILE");
        if (!tokens.length) return faseIndisponivel(conteudo, a, "A lista de tokens");

        const contagem = {};
        tokens.forEach((t) => { const c = categoriaToken(t.tipo); contagem[c] = (contagem[c] || 0) + 1; });
        const resumo = Object.entries(CATEGORIAS_TOKEN).filter(([c]) => contagem[c]).map(([c, info]) =>
            `<span class="chip" style="color:${info.cor}">${contagem[c]} ${info.nome}${contagem[c] > 1 ? "s" : ""}</span>`).join("");
        conteudo.insertAdjacentHTML("beforeend",
            `<p class="secao-titulo">${tokens.length} tokens</p><div class="resumo-tokens">${resumo}</div>`);

        const porLinha = new Map();
        tokens.forEach((t) => { if (!porLinha.has(t.linha)) porLinha.set(t.linha, []); porLinha.get(t.linha).push(t); });
        porLinha.forEach((lista, linha) => {
            const div = document.createElement("div");
            div.className = "linha-tokens";
            div.innerHTML = `<span class="n" title="Ir para a linha">linha ${linha}</span><div class="lista"></div>`;
            div.querySelector(".n").addEventListener("click", () => selecionarLinha(linha));
            const caixa = div.querySelector(".lista");
            lista.forEach((t) => {
                const cat = categoriaToken(t.tipo);
                const cor = CATEGORIAS_TOKEN[cat].cor;
                const lex = t.tipo === "STRING_LITERAL" ? `"${t.lexema}"` : t.lexema;
                const el = document.createElement("span");
                el.className = "token";
                el.style.borderColor = cor + "66";
                el.style.background = cor + "12";
                el.innerHTML = `<span class="lex" style="color:${cor}">${esc(lex)}</span><span class="tipo">${esc(t.tipo)}</span>`;
                el.addEventListener("mouseenter", (ev) => {
                    const fim = t.coluna - 1 + lex.length;
                    destaques.push(editor.markText({ line: t.linha - 1, ch: t.coluna - 1 }, { line: t.linha - 1, ch: fim },
                        { className: "marca-token" }));
                    editor.scrollIntoView({ line: t.linha - 1, ch: 0 }, 80);
                    mostrarDica(ev, `<b>${esc(t.tipo)}</b> · ${CATEGORIAS_TOKEN[cat].nome}<br>linha ${t.linha}, coluna ${t.coluna}`);
                });
                el.addEventListener("mouseleave", () => { limparDestaques(); marcarErrosNoEditor(); esconderDica(); });
                caixa.appendChild(el);
            });
            conteudo.appendChild(div);
        });
    }

    // ------------------------------------------------------------------
    // Fase 2: AST como arvore grafica (D3), de cima para baixo
    // ------------------------------------------------------------------
    function renderAst(conteudo, a) {
        if (!a.ast) return faseIndisponivel(conteudo, a, "A árvore sintática");
        const legenda = Object.values(CORES_CATEGORIA).map((c) =>
            `<span><i style="background:${c.fundo};border:1.5px solid ${c.borda}"></i>${c.nome}</span>`).join("");
        conteudo.innerHTML = `<div class="ast-area">
            <div class="ast-barra">
                <button id="ast-expandir">Expandir tudo</button>
                <button id="ast-recolher">Recolher (2 níveis)</button>
                <button id="ast-centralizar">Centralizar</button>
                <div class="legenda">${legenda}</div>
            </div>
            <svg class="ast-svg" id="ast-svg"></svg></div>`;

        const svg = d3.select("#ast-svg");
        const camada = svg.append("g");
        const zoom = d3.zoom().scaleExtent([0.15, 2.5]).on("zoom", (ev) => camada.attr("transform", ev.transform));
        svg.call(zoom).on("dblclick.zoom", null);

        const raiz = d3.hierarchy(a.ast, (d) => d.filhos);
        raiz.each((n) => { n._filhos = n.children; });
        // Programas grandes comecam recolhidos a partir do 3o nivel (visao geral primeiro)
        const total = raiz.descendants().length;
        if (total > 80) raiz.each((n) => { if (n.depth >= 2 && n.children) n.children = null; });

        const larguraNo = (d) => Math.min(190, Math.max(44, d.data.rotulo.length * 7.4 + 22));
        const ALTURA_NO = 30;

        function desenhar() {
            const layout = d3.tree().nodeSize([1, 86]).separation((x, y) =>
                ((larguraNo(x) + larguraNo(y)) / 2 + 18) * (x.parent === y.parent ? 1 : 1.15));
            layout(raiz);
            const nos = raiz.descendants();
            const ligacoes = raiz.links();

            camada.selectAll("*").remove();
            camada.selectAll("path.ligacao").data(ligacoes).join("path")
                .attr("class", "ligacao")
                .attr("d", d3.linkVertical().x((d) => d.x).y((d) => d.y)
                    .source((l) => ({ x: l.source.x, y: l.source.y + ALTURA_NO / 2 }))
                    .target((l) => ({ x: l.target.x, y: l.target.y - ALTURA_NO / 2 })));
            camada.selectAll("text.papel").data(ligacoes.filter((l) => l.target.data.papel && l.target.data.papel !== "comandos"))
                .join("text").attr("class", "papel").attr("text-anchor", "middle")
                .attr("x", (l) => l.target.x)
                .attr("y", (l) => l.target.y - ALTURA_NO / 2 - 5)   // logo acima do filho: nao colide com irmaos
                .text((l) => l.target.data.papel);

            const g = camada.selectAll("g.no-ast").data(nos).join("g")
                .attr("class", "no-ast").attr("transform", (d) => `translate(${d.x},${d.y})`);
            g.append("rect")
                .attr("x", (d) => -larguraNo(d) / 2).attr("y", -ALTURA_NO / 2)
                .attr("width", larguraNo).attr("height", ALTURA_NO).attr("rx", 7)
                .attr("fill", (d) => (CORES_CATEGORIA[d.data.categoria] || CORES_CATEGORIA.expressao).fundo)
                .attr("stroke", (d) => (CORES_CATEGORIA[d.data.categoria] || CORES_CATEGORIA.expressao).borda)
                .attr("stroke-dasharray", (d) => (!d.children && d._filhos ? "4 3" : null));
            g.append("text").attr("text-anchor", "middle").attr("dy", "0.35em")
                .attr("fill", (d) => (CORES_CATEGORIA[d.data.categoria] || CORES_CATEGORIA.expressao).borda)
                .text((d) => d.data.rotulo);
            g.filter((d) => !d.children && d._filhos).append("text")
                .attr("class", "recolhido").attr("text-anchor", "middle").attr("y", ALTURA_NO / 2 + 12)
                .attr("fill", "#6b7280").text((d) => `+${totalSubarvore(d)} ocultos`);

            g.on("click", (ev, d) => {
                if (d._filhos) { d.children = d.children ? null : d._filhos; desenhar(); }
                selecionarLinha(d.data.linha);
            });
            g.on("mousemove", (ev, d) => {
                const info = Object.entries(d.data.info || {}).map(([k, v]) => `${esc(k)}: ${esc(Array.isArray(v) ? v.join(", ") : v)}`).join("<br>");
                const cat = (CORES_CATEGORIA[d.data.categoria] || {}).nome || "";
                mostrarDica(ev, `<b>${esc(d.data.tipo)}</b> · ${cat}${d.data.papel ? `<br>papel: ${esc(d.data.papel)}` : ""}` +
                    `<br>linha ${d.data.linha}${info ? "<br>" + info : ""}` +
                    (d._filhos ? `<br><i>clique para ${d.children ? "recolher" : "expandir"}</i>` : ""));
            }).on("mouseleave", esconderDica);
        }

        // Total de nos abaixo de um no (para o rotulo "+N ocultos" de um no recolhido)
        function totalSubarvore(no) {
            return (no._filhos || []).reduce((soma, f) => soma + 1 + totalSubarvore(f), 0);
        }

        function centralizar() {
            const caixa = camada.node().getBBox();
            const el = svg.node().getBoundingClientRect();
            if (!caixa.width) return;
            // Encaixa a arvore inteira se couber em escala legivel; senao, mantem a escala
            // minima com a raiz centralizada no topo (o aluno arrasta para explorar)
            const encaixe = 0.92 * Math.min(el.width / caixa.width, el.height / caixa.height);
            const escala = Math.min(1.1, Math.max(0.7, encaixe));
            const centroX = encaixe >= 0.7 ? caixa.x + caixa.width / 2 : raiz.x;
            const tx = el.width / 2 - escala * centroX;
            const ty = 24 - escala * caixa.y;
            svg.transition().duration(300).call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(escala));
        }

        $("ast-expandir").onclick = () => { raiz.each((n) => { n.children = n._filhos; }); desenhar(); centralizar(); };
        $("ast-recolher").onclick = () => { raiz.each((n) => { n.children = n.depth >= 2 ? null : n._filhos; }); desenhar(); centralizar(); };
        $("ast-centralizar").onclick = centralizar;
        desenhar();
        centralizar();
    }

    // ------------------------------------------------------------------
    // Fase 3: Semantica (erros, avisos e tabela de simbolos por escopo)
    // ------------------------------------------------------------------
    function renderSemantico(conteudo, a) {
        if (["LEXICO", "SINTATICO"].includes(a.fase_erro)) return faseIndisponivel(conteudo, a, "A análise semântica");
        const errosSem = a.erros.filter((e) => e.fase === "SEMANTICO");
        conteudo.insertAdjacentHTML("beforeend", errosSem.length
            ? `<div class="estado-semantico erro">✕ ${errosSem.length} erro(s) semântico(s) — veja a lista acima e clique para ir à linha.</div>`
            : `<div class="estado-semantico ok">✓ Nenhum erro semântico${a.avisos.length ? ` (${a.avisos.length} aviso(s))` : ""}.</div>`);

        const porEscopo = new Map();
        (a.simbolos || []).forEach((s) => { if (!porEscopo.has(s.escopo)) porEscopo.set(s.escopo, []); porEscopo.get(s.escopo).push(s); });
        conteudo.insertAdjacentHTML("beforeend", `<p class="secao-titulo">Tabela de símbolos — ${a.simbolos.length} símbolo(s) em ${porEscopo.size} escopo(s)</p>`);
        const grade = document.createElement("div");
        grade.className = "escopos";
        porEscopo.forEach((lista, escopo) => {
            const div = document.createElement("div");
            div.className = "escopo";
            div.innerHTML = `<h4>${esc(escopo)}</h4><table><thead><tr><th>Nome</th><th>Tipo</th><th>Linha</th></tr></thead><tbody></tbody></table>`;
            const corpo = div.querySelector("tbody");
            lista.forEach((s) => {
                const tr = document.createElement("tr");
                const params = s.parametros && s.parametros.length ? `(${s.parametros.join(", ")})` : (s.tipo === "FUNC" ? "()" : "");
                tr.innerHTML = `<td class="mono">${esc(s.nome)}${esc(params)}</td><td>${esc(NOMES_TIPO[s.tipo] || s.tipo)}</td><td>${s.linha}</td>`;
                tr.addEventListener("click", () => selecionarLinha(s.linha));
                corpo.appendChild(tr);
            });
            grade.appendChild(div);
        });
        conteudo.appendChild(grade);
    }

    // ------------------------------------------------------------------
    // Fase 4: TAC com rotulos, temporarios e instrucoes destacados
    // ------------------------------------------------------------------
    function colorirTac(linha) {
        let html = esc(linha);
        const strings = [];
        html = html.replace(/&quot;.*?&quot;/g, (m) => { strings.push(m); return `\u0000${strings.length - 1}\u0000`; });
        html = html.replace(/\/\/.*$/, (m) => `<span class="com">${m}</span>`);
        html = html.replace(/\b(fork|join)\b/g, '<span class="par">$1</span>');
        html = html.replace(/\b(goto|ifFalse|if|param|call|return|func|endfunc|print|send|receive|input|new|core|host)\b/g, '<span class="kw">$1</span>');
        html = html.replace(/\bt\d+\b/g, '<span class="tmp">$&</span>');
        html = html.replace(/\u0000(\d+)\u0000/g, (m, i) => `<span class="str">${strings[+i]}</span>`);
        return html;
    }

    function renderTac(conteudo, a) {
        if (!a.tac) return faseIndisponivel(conteudo, a, "O código de três endereços");
        const linhas = a.tac.replace(/\n$/, "").split("\n");
        const temporarios = new Set((a.tac.match(/\bt\d+\b/g) || []));
        const rotulos = linhas.filter((l) => /^\w+:\s*$/.test(l)).length;
        conteudo.insertAdjacentHTML("beforeend", `<p class="secao-titulo">${linhas.length} instruções · ${temporarios.size} temporários · ${rotulos} rótulos</p>
            <div class="legenda"><span><i style="background:#7c3aed"></i>rótulo (destino de desvio)</span>
            <span><i style="background:#2563eb"></i>instrução</span><span><i style="background:#0d9488"></i>temporário</span>
            <span><i style="background:#ea580c"></i>fork / join</span></div>`);
        const div = document.createElement("div");
        div.className = "tac";
        let dentroDeFuncao = false;
        linhas.forEach((l, i) => {
            const eRotulo = /^\w+:\s*$/.test(l);
            if (/^func /.test(l)) dentroDeFuncao = true;
            const recuo = !eRotulo && !/^(func|endfunc) /.test(l) && dentroDeFuncao;
            if (/^endfunc /.test(l)) dentroDeFuncao = false;
            div.insertAdjacentHTML("beforeend", `<div class="l${recuo ? " recuo" : ""}"><span class="n">${i + 1}</span>` +
                `<span class="codigo">${eRotulo ? `<span class="rotulo">${esc(l)}</span>` : colorirTac(l)}</span></div>`);
        });
        conteudo.appendChild(div);
    }

    // ------------------------------------------------------------------
    // Fase 5: C++ gerado (primeiro o codigo do programa; biblioteca opcional)
    // ------------------------------------------------------------------
    const MARCADOR_CPP = "// ===== Codigo gerado a partir do programa MiniPar =====";
    function renderCpp(conteudo, a) {
        if (!a.cpp) return faseIndisponivel(conteudo, a, "O código C++");
        const i = a.cpp.indexOf(MARCADOR_CPP);
        const doPrograma = i >= 0 ? a.cpp.slice(i) : a.cpp;
        conteudo.innerHTML = `<div class="cpp-opcoes"><label><input type="checkbox" id="cpp-completo">
            Mostrar também a biblioteca de suporte (${i >= 0 ? a.cpp.slice(0, i).split("\n").length : 0} linhas: threads, sockets, listas...)</label></div>
            <div class="cpp-editor"><textarea id="cpp-area"></textarea></div>`;
        cppEditor = CodeMirror.fromTextArea($("cpp-area"), { mode: "text/x-c++src", lineNumbers: true, readOnly: true, viewportMargin: Infinity });
        cppEditor.setValue(doPrograma);
        $("cpp-completo").addEventListener("change", (ev) => cppEditor.setValue(ev.target.checked ? a.cpp : doPrograma));
        setTimeout(() => cppEditor.refresh(), 0);
    }

    // ------------------------------------------------------------------
    // Fase 6: Compilar e baixar o executavel
    // ------------------------------------------------------------------
    function renderCompilar(conteudo, a) {
        if (!a.sucesso) return faseIndisponivel(conteudo, a, "O executável");
        conteudo.innerHTML = `<div class="cartao"><p>O código C++ será compilado com <code>g++ -std=c++20 -O3</code>.</p>
            <button class="botao-primario" id="botao-compilar">Compilar e gerar executável</button>
            <div id="resultado-compilar"></div></div>`;
        $("botao-compilar").addEventListener("click", async (ev) => {
            ev.target.disabled = true;
            ev.target.textContent = "Compilando com g++...";
            const saida = $("resultado-compilar");
            try {
                const r = await postar("compilar", { codigo: editor.getValue() });
                mostrarMensagens(r.erros, r.avisos);
                saida.innerHTML = r.sucesso
                    ? `<div class="cartao sucesso" style="margin-top:14px"><b>✓ Executável gerado.</b><br><br>
                       <a class="botao-primario" style="text-decoration:none;display:inline-block" href="${r.download}">⬇ Baixar executável</a>
                       <p class="nota">No Linux, dê permissão de execução antes de rodar: <code>chmod +x programa_minipar</code> e depois <code>./programa_minipar</code>.<br>
                       Programas com <code>fork ... on host</code> precisam do mesmo executável no outro computador com <code>--worker PORTA</code>.</p></div>`
                    : `<p class="nota">A compilação falhou — veja o erro acima.</p>`;
            } catch (e) {
                saida.innerHTML = `<p class="nota">${esc(e.message)}</p>`;
            }
            ev.target.disabled = false;
            ev.target.textContent = "Compilar novamente";
        });
    }

    // ------------------------------------------------------------------
    // Fase 7: Executar
    // ------------------------------------------------------------------
    function renderExecutar(conteudo, a) {
        if (!a.sucesso) return faseIndisponivel(conteudo, a, "O programa");
        const usaInput = (a.tokens || []).some((t) => t.tipo === "INPUT");
        conteudo.innerHTML = `<div class="cartao">
            <label for="entradas"><b>Entradas</b> <span class="nota">(valores para input(), um por linha${usaInput ? " — este programa usa input()" : ""})</span></label>
            <textarea class="entradas" id="entradas" placeholder="${usaInput ? "ex.: 10 -3 -40 80" : "este programa não lê entradas"}"></textarea>
            <div style="margin-top:10px"><button class="botao-primario" id="botao-executar">▶ Compilar e executar</button></div></div>
            <p class="secao-titulo">Saída</p><div class="terminal" id="terminal"><span class="meta">A saída do programa aparecerá aqui.</span></div>`;
        $("botao-executar").addEventListener("click", async (ev) => {
            ev.target.disabled = true;
            ev.target.textContent = "Executando...";
            const terminal = $("terminal");
            terminal.innerHTML = `<span class="meta">Compilando e executando...</span>`;
            try {
                const entradas = $("entradas").value.split("\n").filter((l, i, v) => l !== "" || i < v.length - 1);
                const r = await postar("executar", { codigo: editor.getValue(), entradas });
                mostrarMensagens(r.erros, r.avisos);
                if (!r.sucesso) { terminal.innerHTML = `<span class="stderr">A compilação falhou — veja o erro acima.</span>`; }
                else {
                    let html = esc(r.saida || "");
                    if (r.erros_execucao) html += `<span class="stderr">${esc(r.erros_execucao)}</span>`;
                    if (r.tempo_limite) html += `<span class="stderr">\n[Tempo limite excedido: o programa foi interrompido. Laço infinito ou espera por um computador remoto?]</span>`;
                    if (r.saida_truncada) html += `<span class="stderr">\n[Saída muito grande: o programa foi interrompido.]</span>`;
                    const fim = r.codigo_saida === null ? "interrompido" : `código de saída ${r.codigo_saida}`;
                    html += `<span class="meta">\n— ${fim} · ${r.tempo_execucao.toFixed(2)} s</span>`;
                    terminal.innerHTML = html;
                }
            } catch (e) {
                terminal.innerHTML = `<span class="stderr">${esc(e.message)}</span>`;
            }
            ev.target.disabled = false;
            ev.target.textContent = "▶ Executar novamente";
        });
    }

    // ------------------------------------------------------------------
    // Exemplos (testes do projeto)
    // ------------------------------------------------------------------
    async function carregarListaExemplos() {
        const r = await fetch("/api/tests");
        const { tests } = await r.json();
        const sel = $("exemplos");
        tests.forEach((t) => sel.insertAdjacentHTML("beforeend", `<option value="${esc(t)}">${esc(t.replace(".minipar", ""))}</option>`));
        sel.addEventListener("change", () => sel.value && carregarExemplo(sel.value));
    }

    async function carregarExemplo(arquivo, fase) {
        const r = await fetch("/api/get_test", {
            method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ filename: arquivo }),
        });
        const d = await r.json();
        if (d.code === undefined) return;
        editor.setValue(d.code);
        $("exemplos").value = arquivo;
        analise = null;
        atualizarEstados();
        $("erros").hidden = true;
        abrirFase(fase || faseAtual || "tokens");
    }

    // ------------------------------------------------------------------
    // Inicio. Parametros opcionais na URL: ?exemplo=arquivo.minipar&fase=ast
    // ------------------------------------------------------------------
    document.addEventListener("DOMContentLoaded", async () => {
        iniciarEditor();
        montarPipeline();
        editor.setValue('# Exemplo: fork e join\nfunc quadrado(x) {\n    return x * x;\n}\n\nfork t1 = quadrado(7) on core 0;\nfork t2 = quadrado(8) on core 1;\nprint("Soma dos quadrados:", join t1 + join t2);\n');
        await carregarListaExemplos();
        const p = new URLSearchParams(location.search);
        if (p.get("exemplo")) await carregarExemplo(p.get("exemplo"), p.get("fase"));
        else if (p.get("fase")) abrirFase(p.get("fase"));
    });
})();
