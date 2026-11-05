_CPP_HEADER = """\
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
std::vector<double> __parse_ints(const std::string& s) {
    std::vector<double> result;
    std::istringstream iss(s);
    double n;
    while (iss >> n) {
        result.push_back(n);
    }
    return result;
}

std::vector<int> __minipar_range(int end) {
    std::vector<int> values;
    for (int i = 0; i < end; ++i) values.push_back(i);
    return values;
}

std::vector<int> __minipar_range(int start, int end) {
    std::vector<int> values;
    for (int i = start; i < end; ++i) values.push_back(i);
    return values;
}

// Helper para Arrays (.pop) do Python
template<typename T>
auto __array_pop(std::vector<T>& v) {
    if (v.empty()) return T{};
    auto val = v.back();
    v.pop_back();
    return val;
}

// Helper para formatar e printar std::vector (arrays e matrizes) nativamente
template <typename T>
std::ostream& operator<<(std::ostream& os, const std::vector<T>& v) {
    os << "[";
    for (size_t i = 0; i < v.size(); ++i) {
        os << v[i];
        if (i != v.size() - 1) os << ", ";
    }
    os << "]";
    return os;
}

template<typename T>
std::string __to_string(const T& val) {
    if constexpr (std::is_constructible_v<std::string, T>) {
        return std::string(val);
    } else {
        return std::to_string(val);
    }
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

"""
