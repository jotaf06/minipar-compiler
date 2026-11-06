_CPP_HEADER = """\
#ifdef _WIN32
  // Windows 7+: necessario para GetCurrentProcessorNumber (funcao nucleo())
  #ifndef _WIN32_WINNT
    #define _WIN32_WINNT 0x0601
  #endif
#endif
#include <iostream>
#include <string>
#include <sstream>
#include <vector>
#include <thread>
#include <memory>
#include <cstring>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <type_traits>
#include <mutex>
#include <algorithm>
#include <charconv>
#include <iomanip>
#include <future>
#include <fstream>
#ifndef _WIN32
  #include <pthread.h>
  #include <sched.h>
#endif

#ifdef _WIN32
  #include <winsock2.h>
  #include <ws2tcpip.h>
  #pragma comment(lib, "ws2_32.lib")
  #define CLOSE_SOCK closesocket
#else
  #include <sys/socket.h>
  #include <arpa/inet.h>
  #include <unistd.h>
  #define CLOSE_SOCK close
#endif

// Helper para Random nativo
double random_val() { return (double)rand() / RAND_MAX; }

// Helper para Input
std::string input() {
    std::string s;
    std::getline(std::cin, s);
    return s;
}

std::string input(const std::string& prompt) {
    std::cout << prompt;
    return input();
}

// Converte linha com inteiros separados por espaco em vetor (ex.: "10 -3 80")
std::vector<long long> __parse_ints(const std::string& s) {
    std::vector<long long> result;
    std::istringstream iss(s);
    long long n;
    while (iss >> n) {
        result.push_back(n);
    }
    return result;
}

std::vector<long long> __minipar_range(long long end) {
    std::vector<long long> values;
    for (long long i = 0; i < end; ++i) values.push_back(i);
    return values;
}

std::vector<long long> __minipar_range(long long start, long long end) {
    std::vector<long long> values;
    for (long long i = start; i < end; ++i) values.push_back(i);
    return values;
}

// ---------------------------------------------------------------------------
// Erros em tempo de execucao: mensagem clara e fim do programa (como o Python)
// ---------------------------------------------------------------------------
// Dentro de uma subtarefa remota (modo --worker) o erro nao encerra o trabalhador:
// vira uma excecao, e a mensagem e devolvida ao computador principal
struct __ErroRemoto { std::string msg; };
inline thread_local bool __em_subtarefa_remota = false;

[[noreturn]] void __erro_execucao(const std::string& msg) {
    if (__em_subtarefa_remota) throw __ErroRemoto{msg};
    std::cout.flush();
    std::cerr << "[ERRO DE EXECUCAO] " << msg << std::endl;
    std::exit(1);
}

// ---------------------------------------------------------------------------
// Operadores numericos com a semantica do Python 3
// ---------------------------------------------------------------------------
// a / b  -> divisao real (3 / 2 == 1.5)
template<typename A, typename B>
inline double __div(A a, B b) {
    if (b == 0) __erro_execucao("Divisao por zero");
    return static_cast<double>(a) / static_cast<double>(b);
}

// a // b -> divisao inteira arredondada para baixo (-7 // 2 == -4)
template<typename A, typename B>
inline auto __floordiv(A a, B b) {
    if (b == 0) __erro_execucao("Divisao inteira por zero");
    if constexpr (std::is_integral_v<A> && std::is_integral_v<B>) {
        long long q = static_cast<long long>(a) / static_cast<long long>(b);
        if ((a % b != 0) && ((a < 0) != (b < 0))) q--;
        return q;
    } else {
        return std::floor(static_cast<double>(a) / static_cast<double>(b));
    }
}

// a % b  -> resto com o sinal do divisor (-7 % 3 == 2), tambem para reais
template<typename A, typename B>
inline auto __mod(A a, B b) {
    if (b == 0) __erro_execucao("Modulo por zero");
    if constexpr (std::is_integral_v<A> && std::is_integral_v<B>) {
        long long r = static_cast<long long>(a) % static_cast<long long>(b);
        if (r != 0 && ((r < 0) != (b < 0))) r += b;
        return r;
    } else {
        double r = std::fmod(static_cast<double>(a), static_cast<double>(b));
        if (r != 0 && ((r < 0) != (b < 0))) r += b;
        return r;
    }
}

// Operadores bit a bit (&, |, ^, <<, >>) sempre sobre inteiros de 64 bits
template<typename T>
inline long long __as_int(T v) { return static_cast<long long>(v); }

// Helper para Arrays (.pop) do Python
template<typename T>
auto __array_pop(std::vector<T>& v) {
    if (v.empty()) return T{};
    auto val = v.back();
    v.pop_back();
    return val;
}

// Listas sao impressas como no Python: [1, 2.5, 3] (elementos via __to_string)
template<typename T> std::string __to_string(const T& val);

template <typename T>
std::ostream& operator<<(std::ostream& os, const std::vector<T>& v) {
    os << "[";
    for (size_t i = 0; i < v.size(); ++i) {
        os << __to_string(v[i]);
        if (i != v.size() - 1) os << ", ";
    }
    os << "]";
    return os;
}

// ---------------------------------------------------------------------------
// Strings e listas
// ---------------------------------------------------------------------------
template<typename T> struct __is_vector : std::false_type {};
template<typename T, typename A> struct __is_vector<std::vector<T, A>> : std::true_type {};

template<typename T>
constexpr bool __is_texto_v = std::is_same_v<std::decay_t<T>, std::string>
                           || std::is_same_v<std::decay_t<T>, const char*>
                           || std::is_same_v<std::decay_t<T>, char*>
                           || std::is_same_v<std::decay_t<T>, char>;

// Real no formato do Python: menor representacao que preserva o valor
// (0.1 -> "0.1", 2.0 -> "2.0", 1e-05 -> "1e-05", 1e+16 -> "1e+16")
inline std::string __real_para_texto(double v) {
    if (std::isnan(v)) return "nan";
    if (std::isinf(v)) return v > 0 ? "inf" : "-inf";
    char buf[64];
    double a = std::fabs(v);
    bool cientifico = (a != 0.0) && (a < 1e-4 || a >= 1e16);
    auto res = std::to_chars(buf, buf + sizeof(buf), v,
                             cientifico ? std::chars_format::scientific : std::chars_format::fixed);
    std::string s(buf, res.ptr);
    if (!cientifico && s.find('.') == std::string::npos) s += ".0";
    return s;
}

// Converte qualquer valor para texto, como o str() do Python
// (usado por print, +, str(), send e join_str)
template<typename T>
std::string __to_string(const T& val) {
    using D = std::decay_t<T>;
    if constexpr (std::is_same_v<D, bool> || std::is_same_v<D, std::vector<bool>::reference>) {
        return static_cast<bool>(val) ? "True" : "False";
    } else if constexpr (std::is_same_v<D, char>) {
        return std::string(1, val);
    } else if constexpr (std::is_constructible_v<std::string, T>) {
        return std::string(val);
    } else if constexpr (std::is_floating_point_v<D>) {
        return __real_para_texto(static_cast<double>(val));
    } else if constexpr (std::is_integral_v<D>) {
        return std::to_string(val);
    } else {
        std::ostringstream os;   // listas, matrizes e demais tipos com operator<<
        os << val;
        return os.str();
    }
}

// print(a, b, ...): valores separados por espaco, como no Python. A linha inteira e
// montada antes e escrita de uma vez sob um mutex, para que threads (blocos par)
// nao misturem os caracteres de linhas diferentes.
inline std::mutex& __print_mutex() { static std::mutex m; return m; }

template<typename... Args>
void __print(const Args&... args) {
    std::string linha;
    bool primeiro = true;
    ((linha += (primeiro ? "" : " ") + __to_string(args), primeiro = false), ...);
    linha += '\\n';
    std::lock_guard<std::mutex> lock(__print_mutex());
    std::cout << linha << std::flush;
}

// str(x)
template<typename T>
inline std::string __str(const T& x) { return __to_string(x); }

// format(x, casas): real com numero fixo de casas decimais (f"{x:.2f}" do Python)
template<typename T, typename C>
inline std::string __format(const T& x, C casas) {
    std::ostringstream os;
    os << std::fixed << std::setprecision(static_cast<int>(casas)) << static_cast<double>(x);
    return os.str();
}

// to_int(x): parte inteira (trunca em direcao ao zero) ou conversao de texto
template<typename T>
inline long long __to_int(const T& x) {
    if constexpr (__is_texto_v<T>) {
        try { return std::stoll(__to_string(x)); }
        catch (...) { __erro_execucao("to_int: valor invalido '" + __to_string(x) + "'"); }
    } else {
        return static_cast<long long>(x);
    }
}

// to_number(x): numero real a partir de texto ou numero
template<typename T>
inline double __to_number(const T& x) {
    if constexpr (__is_texto_v<T>) {
        try { return std::stod(__to_string(x)); }
        catch (...) { __erro_execucao("to_number: valor invalido '" + __to_string(x) + "'"); }
    } else {
        return static_cast<double>(x);
    }
}

// write_file(caminho, texto): grava o texto em um arquivo (ex.: desenho SVG)
inline void __write_file(const std::string& caminho, const std::string& texto) {
    std::ofstream arquivo(caminho, std::ios::binary);
    if (!arquivo) __erro_execucao("Nao foi possivel criar o arquivo '" + caminho + "'");
    arquivo << texto;
}

// clock(): tempo em segundos de alta precisao (time.perf_counter() do Python)
inline double __clock() {
    using namespace std::chrono;
    return duration<double>(steady_clock::now().time_since_epoch()).count();
}

// ---------------------------------------------------------------------------
// Fork / Join: cada fork vira uma tarefa assincrona (std::async) com o resultado
// em um std::shared_future; join espera (wait) ou recolhe o valor (get).
// ---------------------------------------------------------------------------
inline int __num_nucleos() {
    unsigned n = std::thread::hardware_concurrency();
    return n ? static_cast<int>(n) : 1;
}

// Fixa a thread atual em um nucleo da CPU (core < 0: deixa o sistema escolher)
inline void __fixar_nucleo(long long core) {
    if (core < 0) return;
    int n = __num_nucleos();
    int c = static_cast<int>(core % n);
    if (core >= n) {
        std::lock_guard<std::mutex> lock(__print_mutex());
        std::cerr << "[AVISO] Nucleo " << core << " nao existe (esta maquina tem " << n
                  << "); usando o nucleo " << c << "." << std::endl;
    }
#if defined(_WIN32)
    SetThreadAffinityMask(GetCurrentThread(), static_cast<DWORD_PTR>(1) << c);
#elif defined(__linux__)
    cpu_set_t conjunto;
    CPU_ZERO(&conjunto);
    CPU_SET(c, &conjunto);
    pthread_setaffinity_np(pthread_self(), sizeof(conjunto), &conjunto);
#else
    (void)c;   // macOS e outros: o sistema nao permite fixar a thread em um nucleo
#endif
}

// nucleo(): numero do nucleo da CPU em que a thread atual esta executando
inline long long __nucleo() {
#if defined(_WIN32)
    return static_cast<long long>(GetCurrentProcessorNumber());
#elif defined(__linux__)
    return static_cast<long long>(sched_getcpu());
#else
    return -1;   // indisponivel nesta plataforma
#endif
}

// fork: os argumentos ja foram copiados para a tarefa (captura por valor), entao a
// subtarefa trabalha sobre seus proprios dados, como um processo independente
template<typename F>
auto __fork(long long core, F tarefa) {
    return std::async(std::launch::async, [core, tarefa]() mutable {
        __fixar_nucleo(core);
        return tarefa();
    }).share();
}

// a + b: soma numerica, concatenacao de texto (convertendo o outro lado) ou de listas
template<typename A, typename B>
inline auto __add(const A& a, const B& b) {
    if constexpr (__is_texto_v<A> || __is_texto_v<B>) {
        return __to_string(a) + __to_string(b);
    } else if constexpr (__is_vector<A>::value && __is_vector<B>::value) {
        A r = a;
        r.insert(r.end(), b.begin(), b.end());
        return r;
    } else {
        return a + b;
    }
}

// Literais de lista: tipo definido pelo semantico (__lista_t) ou deduzido (__lista)
template<typename T, typename... Args>
std::vector<T> __lista_t(const Args&... args) {
    std::vector<T> v;
    v.reserve(sizeof...(Args));
    (v.push_back(static_cast<T>(args)), ...);
    return v;
}

template<typename... Args>
auto __lista(const Args&... args) {
    using T = std::common_type_t<std::decay_t<Args>...>;
    return __lista_t<T>(args...);
}

template<typename T>
inline long long __len(const T& x) { return static_cast<long long>(x.size()); }

[[noreturn]] inline void __erro_indice(long long i, std::size_t n) {
    __erro_execucao("Indice " + std::to_string(i) + " fora dos limites (tamanho "
                    + std::to_string(n) + ")");
}

// Leitura lista[i] / texto[i]: indices negativos contam do fim, como no Python
template<typename T, typename I>
inline T& __index(std::vector<T>& v, I idx) {
    long long i = static_cast<long long>(idx);
    if (i < 0) i += static_cast<long long>(v.size());
    if (i < 0 || i >= static_cast<long long>(v.size())) __erro_indice(static_cast<long long>(idx), v.size());
    return v[i];
}

template<typename T, typename I>
inline const T& __index(const std::vector<T>& v, I idx) {
    long long i = static_cast<long long>(idx);
    if (i < 0) i += static_cast<long long>(v.size());
    if (i < 0 || i >= static_cast<long long>(v.size())) __erro_indice(static_cast<long long>(idx), v.size());
    return v[i];
}

template<typename I>
inline std::string __index(const std::string& s, I idx) {
    long long i = static_cast<long long>(idx);
    if (i < 0) i += static_cast<long long>(s.size());
    if (i < 0 || i >= static_cast<long long>(s.size())) __erro_indice(static_cast<long long>(idx), s.size());
    return std::string(1, s[i]);
}

// Listas de logicos: std::vector<bool> e compactado (1 bit por elemento) e nao
// devolve bool&, mas um objeto "proxy"; por isso precisa de versoes proprias.
template<typename I>
inline std::vector<bool>::reference __index(std::vector<bool>& v, I idx) {
    long long i = static_cast<long long>(idx);
    if (i < 0) i += static_cast<long long>(v.size());
    if (i < 0 || i >= static_cast<long long>(v.size())) __erro_indice(static_cast<long long>(idx), v.size());
    return v[i];
}

template<typename I>
inline bool __index(const std::vector<bool>& v, I idx) {
    long long i = static_cast<long long>(idx);
    if (i < 0) i += static_cast<long long>(v.size());
    if (i < 0 || i >= static_cast<long long>(v.size())) __erro_indice(static_cast<long long>(idx), v.size());
    return v[i];
}

template<typename I>
inline std::vector<bool>::reference __index_set(std::vector<bool>& v, I idx) {
    long long i = static_cast<long long>(idx);
    if (i < 0) i += static_cast<long long>(v.size());
    if (i < 0) __erro_indice(static_cast<long long>(idx), v.size());
    if (i >= static_cast<long long>(v.size())) v.resize(i + 1);
    return v[i];
}

// Escrita lista[i] = v: alem do fim, a lista cresce (comportamento de pilha)
template<typename T, typename I>
inline T& __index_set(std::vector<T>& v, I idx) {
    long long i = static_cast<long long>(idx);
    if (i < 0) i += static_cast<long long>(v.size());
    if (i < 0) __erro_indice(static_cast<long long>(idx), v.size());
    if (i >= static_cast<long long>(v.size())) v.resize(i + 1);
    return v[i];
}

// slice(x, a, b): fatia x[a:b] de lista ou texto (indices como no Python)
template<typename T, typename A, typename B>
T __slice(const T& x, A a, B b) {
    long long n = static_cast<long long>(x.size());
    long long ini = static_cast<long long>(a), fim = static_cast<long long>(b);
    if (ini < 0) ini += n;
    if (fim < 0) fim += n;
    ini = std::max(0LL, std::min(ini, n));
    fim = std::max(0LL, std::min(fim, n));
    if (fim <= ini) return T{};
    return T(x.begin() + ini, x.begin() + fim);
}

// join_str(lista, sep): junta os elementos como texto (equivale a sep.join(lista) do Python)
template<typename T>
std::string __join_str(const std::vector<T>& lista, const std::string& sep) {
    std::string r;
    for (std::size_t i = 0; i < lista.size(); ++i) {
        if (i > 0) r += sep;
        r += __to_string(lista[i]);
    }
    return r;
}

template<typename T>
auto __make_matrix(int rows, int cols, T init_val) {
    using ActualT = std::conditional_t<std::is_same_v<std::decay_t<T>, const char*>, std::string, T>;
    return std::vector<std::vector<ActualT>>(rows, std::vector<ActualT>(cols, init_val));
}

class MiniParChannel {
public:
    std::string ip;
    int port;

    MiniParChannel(std::string ip, int port) : ip(ip), port(port) {}

    void sendData(std::string msg) {
        struct sockaddr_in serv_addr;
        std::memset(&serv_addr, 0, sizeof(serv_addr));
        serv_addr.sin_family = AF_INET;
        serv_addr.sin_port = htons(port);
        inet_pton(AF_INET, ip.c_str(), &serv_addr.sin_addr);

        // Tenta conectar ate o receptor estar escutando (ate ~10 s).
        // Um socket cujo connect() falhou nao pode ser reutilizado (no Linux),
        // por isso cada tentativa cria um socket novo.
        for (int i = 0; i < 100; i++) {
            int sock = socket(AF_INET, SOCK_STREAM, 0);
            if (sock < 0) return;
            if (connect(sock, (struct sockaddr*)&serv_addr, sizeof(serv_addr)) >= 0) {
                send(sock, msg.c_str(), msg.length(), 0);
                CLOSE_SOCK(sock);
                return;
            }
            CLOSE_SOCK(sock);
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
        std::cerr << "[ERRO] Canal " << ip << ":" << port << " indisponivel." << std::endl;
    }

    std::string receiveData() {
        std::lock_guard<std::mutex> lock(recv_mutex);
        if (!ensureListening()) return "";

        int conn = accept(listen_fd, nullptr, nullptr);
        if (conn < 0) return "";

        // Le ate o remetente fechar a conexao (1 conexao = 1 mensagem),
        // permitindo mensagens maiores que o buffer (ex.: fractais em ASCII).
        std::string result;
        char buffer[4096];
        while (true) {
            int n = recv(conn, buffer, sizeof(buffer), 0);
            if (n <= 0) break;
            result.append(buffer, n);
        }
        CLOSE_SOCK(conn);
        return result;
    }

    ~MiniParChannel() {
        if (listen_fd >= 0) CLOSE_SOCK(listen_fd);
    }

private:
    // Socket de escuta persistente: criado no primeiro receive e mantido aberto.
    // Assim, mensagens enviadas antes do proximo receive ficam na fila (backlog)
    // em vez de serem perdidas quando o socket era fechado a cada recebimento.
    int listen_fd = -1;
    std::mutex recv_mutex;

    bool ensureListening() {
        if (listen_fd >= 0) return true;
        int fd = socket(AF_INET, SOCK_STREAM, 0);
        if (fd < 0) return false;
        int opt = 1;
        setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, (const char*)&opt, sizeof(opt));

        struct sockaddr_in address;
        std::memset(&address, 0, sizeof(address));
        address.sin_family = AF_INET;
        address.sin_addr.s_addr = INADDR_ANY;
        address.sin_port = htons(port);

        if (bind(fd, (struct sockaddr*)&address, sizeof(address)) < 0 || listen(fd, 64) < 0) {
            std::cerr << "[ERRO] Nao foi possivel escutar na porta " << port << std::endl;
            CLOSE_SOCK(fd);
            return false;
        }
        listen_fd = fd;
        return true;
    }
};


// ===========================================================================
// Fork remoto (on host "ip":porta) - MiniPar 2026.2
// O MESMO executavel roda no outro computador em modo trabalhador:
//     ./programa --worker 5400
// O fork envia "id|argumentos" (texto), o trabalhador executa a funcao e devolve
// "R|resultado" (ou "E|mensagem" em caso de erro). 1 conexao TCP = 1 subtarefa.
// ===========================================================================

// ---- Serializacao: cada valor vira texto com uma etiqueta de tipo ----
//   inteiro i<n>;   real d<n>;   logico b0; b1;   texto s<tam>:<bytes>   lista l<tam>:<elementos>
template<typename T>
void __ser(std::string& o, const T& v) {
    if constexpr (std::is_same_v<T, bool>) {
        o += v ? "b1;" : "b0;";
    } else if constexpr (std::is_integral_v<T>) {
        o += "i" + std::to_string(static_cast<long long>(v)) + ";";
    } else if constexpr (std::is_floating_point_v<T>) {
        char buf[64];
        auto res = std::to_chars(buf, buf + sizeof(buf), static_cast<double>(v));
        o += "d";
        o.append(buf, res.ptr);
        o += ";";
    } else if constexpr (std::is_same_v<T, std::string>) {
        o += "s" + std::to_string(v.size()) + ":" + v;
    } else if constexpr (__is_vector<T>::value) {
        o += "l" + std::to_string(v.size()) + ":";
        for (std::size_t i = 0; i < v.size(); ++i)
            __ser(o, static_cast<typename T::value_type>(v[i]));
    } else {
        static_assert(sizeof(T) == 0, "tipo nao pode ser enviado a outro computador");
    }
}

struct __Leitor {
    const std::string& s;
    std::size_t p = 0;
};

inline std::string __ler_ate(__Leitor& l, char fim) {
    std::size_t f = l.s.find(fim, l.p);
    if (f == std::string::npos) __erro_execucao("Mensagem remota incompleta");
    std::string r = l.s.substr(l.p, f - l.p);
    l.p = f + 1;
    return r;
}

inline void __esperar_etiqueta(__Leitor& l, char etiqueta) {
    if (l.p >= l.s.size() || l.s[l.p] != etiqueta)
        __erro_execucao(std::string("Mensagem remota invalida (esperado tipo '") + etiqueta + "')");
    l.p++;
}

template<typename T>
T __des(__Leitor& l) {
    if constexpr (std::is_same_v<T, bool>) {
        __esperar_etiqueta(l, 'b');
        return __ler_ate(l, ';') == "1";
    } else if constexpr (std::is_integral_v<T>) {
        __esperar_etiqueta(l, 'i');
        return static_cast<T>(std::stoll(__ler_ate(l, ';')));
    } else if constexpr (std::is_floating_point_v<T>) {
        __esperar_etiqueta(l, 'd');
        return static_cast<T>(std::stod(__ler_ate(l, ';')));
    } else if constexpr (std::is_same_v<T, std::string>) {
        __esperar_etiqueta(l, 's');
        std::size_t n = std::stoull(__ler_ate(l, ':'));
        if (l.p + n > l.s.size()) __erro_execucao("Mensagem remota incompleta");
        std::string r = l.s.substr(l.p, n);
        l.p += n;
        return r;
    } else if constexpr (__is_vector<T>::value) {
        __esperar_etiqueta(l, 'l');
        std::size_t n = std::stoull(__ler_ate(l, ':'));
        T r;
        r.reserve(n);
        for (std::size_t i = 0; i < n; ++i) r.push_back(__des<typename T::value_type>(l));
        return r;
    } else {
        static_assert(sizeof(T) == 0, "tipo nao pode ser recebido de outro computador");
    }
}

// ---- Envio e recebimento completos por uma conexao TCP ----
inline bool __enviar_tudo(int sock, const std::string& dados) {
    std::size_t enviado = 0;
    while (enviado < dados.size()) {
        int n = send(sock, dados.data() + enviado, static_cast<int>(dados.size() - enviado), 0);
        if (n <= 0) return false;
        enviado += static_cast<std::size_t>(n);
    }
    return true;
}

inline std::string __receber_tudo(int sock) {
    std::string r;
    char buf[4096];
    while (true) {
        int n = recv(sock, buf, sizeof(buf), 0);
        if (n <= 0) break;
        r.append(buf, n);
    }
    return r;
}

// ---- Lado do programa principal: executa uma subtarefa em outro computador ----
// Gerada pelo compilador: identifica a versao do programa nos pedidos remotos
extern const char* const __ASSINATURA_PROGRAMA;

inline void __validar_porta(long long porta) {
    if (porta < 1 || porta > 65535)
        __erro_execucao("Porta " + std::to_string(porta) + " invalida (use de 1 a 65535)");
}

template<typename R, typename... Args>
R __remoto(const std::string& ip, long long porta, int id, const Args&... args) {
    __validar_porta(porta);
    // Pedido: assinatura do programa | numero da subtarefa | argumentos serializados
    std::string pedido = std::string(__ASSINATURA_PROGRAMA) + "|" + std::to_string(id) + "|";
    (__ser(pedido, args), ...);

    struct sockaddr_in destino;
    std::memset(&destino, 0, sizeof(destino));
    destino.sin_family = AF_INET;
    destino.sin_port = htons(static_cast<unsigned short>(porta));
    if (inet_pton(AF_INET, ip.c_str(), &destino.sin_addr) != 1)
        __erro_execucao("Endereco invalido em 'on host': " + ip);

    // Tenta conectar por ate ~10 s no total (o trabalhador pode estar iniciando)
    int sock = -1;
    auto limite = std::chrono::steady_clock::now() + std::chrono::seconds(10);
    while (sock < 0 && std::chrono::steady_clock::now() < limite) {
        int s = static_cast<int>(socket(AF_INET, SOCK_STREAM, 0));
        if (s >= 0 && connect(s, (struct sockaddr*)&destino, sizeof(destino)) >= 0) { sock = s; break; }
        if (s >= 0) CLOSE_SOCK(s);
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    if (sock < 0)
        __erro_execucao("Computador " + ip + ":" + std::to_string(porta) + " indisponivel. "
                        "Inicie la o mesmo programa com: --worker " + std::to_string(porta));

    __enviar_tudo(sock, pedido);
    shutdown(sock, 1);                       // fim do pedido (SHUT_WR / SD_SEND)
    std::string resposta = __receber_tudo(sock);
    CLOSE_SOCK(sock);

    if (resposta.rfind("E|", 0) == 0) __erro_execucao("Computador remoto: " + resposta.substr(2));
    if (resposta.rfind("R|", 0) != 0)
        __erro_execucao("O computador " + ip + " encerrou a subtarefa sem responder");
    if constexpr (!std::is_void_v<R>) {
        __Leitor l{resposta, 2};
        return __des<R>(l);
    }
}

// Gerados pelo compilador para cada programa (tabela de subtarefas remotas)
std::string __executar_remoto(int id, __Leitor& l);
void __iniciar_globais();

template<typename F>
std::string __resposta(F chamada) {
    if constexpr (std::is_void_v<decltype(chamada())>) {
        chamada();
        return "R|";
    } else {
        std::string o = "R|";
        __ser(o, chamada());
        return o;
    }
}

// ---- Lado do trabalhador: atende subtarefas, cada uma em sua propria thread ----
inline void __servir_remoto(long long porta) {
    __validar_porta(porta);
    int fd = static_cast<int>(socket(AF_INET, SOCK_STREAM, 0));
    int opt = 1;
    setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, (const char*)&opt, sizeof(opt));
    struct sockaddr_in endereco;
    std::memset(&endereco, 0, sizeof(endereco));
    endereco.sin_family = AF_INET;
    endereco.sin_addr.s_addr = INADDR_ANY;
    endereco.sin_port = htons(static_cast<unsigned short>(porta));
    if (fd < 0 || bind(fd, (struct sockaddr*)&endereco, sizeof(endereco)) < 0 || listen(fd, 64) < 0)
        __erro_execucao("Nao foi possivel escutar na porta " + std::to_string(porta));

    __print("[WORKER] Aguardando subtarefas na porta", porta, "| nucleos disponiveis:", __num_nucleos());
    while (true) {
        int conexao = static_cast<int>(accept(fd, nullptr, nullptr));
        if (conexao < 0) continue;
        std::thread([conexao]() {
            __em_subtarefa_remota = true;
            std::string pedido = __receber_tudo(conexao);
            std::string resposta;
            std::size_t b1 = pedido.find('|');
            std::size_t b2 = (b1 == std::string::npos) ? b1 : pedido.find('|', b1 + 1);
            if (b2 == std::string::npos) {
                resposta = "E|pedido invalido";
            } else if (pedido.substr(0, b1) != __ASSINATURA_PROGRAMA) {
                resposta = "E|o trabalhador esta executando outra versao do programa "
                           "(compile o mesmo .minipar nos dois computadores)";
                __print("[WORKER] Pedido recusado: versao diferente do programa");
            } else {
                int id = std::atoi(pedido.substr(b1 + 1, b2 - b1 - 1).c_str());
                __Leitor l{pedido, b2 + 1};
                __print("[WORKER] Executando subtarefa", id, "no nucleo", __nucleo());
                try {
                    resposta = __executar_remoto(id, l);
                } catch (const __ErroRemoto& e) {
                    resposta = "E|" + e.msg;
                    __print("[WORKER] Erro na subtarefa", id, ":", e.msg);
                } catch (const std::exception& e) {
                    resposta = std::string("E|") + e.what();
                    __print("[WORKER] Erro na subtarefa", id, ":", e.what());
                }
            }
            __enviar_tudo(conexao, resposta);
            CLOSE_SOCK(conexao);
        }).detach();
    }
}

"""
