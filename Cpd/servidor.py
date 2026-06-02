"""
servidor.py
===========
Servidor RPC implementado sobre sockets TCP.

Disponibiliza remotamente as funcionalidades da Componente 1:
  - find_max_prime(timeout)
  - is_prime(n)
  - game_of_life(grid, generations)
  - list_methods()

Notas:

1) Porque usamos threads para os clientes e nao processos?
   O servidor e principalmente I/O-bound: passa a maior parte do tempo
   a aguardar dados da rede. Para este padrao, threads sao suficientes
   e muito mais leves do que processos.
   As funcoes CPU-bound (find_max_prime, game_of_life) ja gerem o seu
   proprio paralelismo internamente via multiprocessing.

2) Como funciona o despacho de metodos?
   Usamos um dicionario METHODS que mapeia nome -> funcao handler.
   Isto evita if/elif encadeados e permite adicionar novos metodos
   facilmente sem tocar na logica do servidor.

3) Como e feita a validacao dos pedidos?
   Antes de invocar qualquer funcao, verificamos:
   - se o JSON e valido;
   - se os campos method e params existem;
   - se o metodo existe no dicionario;
   - se os parametros esperados estao todos presentes e nao ha extras.
   Qualquer erro devolve {"error": "mensagem"} ao cliente.

4) Como e garantida a robustez perante falhas de rede?
   Cada cliente corre numa thread separada com try/finally que fecha
   sempre o socket, mesmo que ocorra uma excecao inesperada.
   O servidor principal continua a aceitar ligacoes mesmo que uma
   thread de cliente falhe.

5) Formato das mensagens
   Cada mensagem e uma linha JSON terminada em newline ('\n').
   O buffer acumula dados ate encontrar '\n', o que resolve o problema
   de fragmentacao TCP (uma mensagem pode chegar em varios pacotes).

6) Como usar:
   python servidor.py        -> escuta em 0.0.0.0:9000 (por omissao)
   python servidor.py 9001   -> escuta na porta 9001
"""

import socket
import threading
import json
import inspect
import sys

from primos import is_prime, find_max_prime_parallel
from game_of_life import game_of_life_parallel

# configuracao do servidor
HOST = "0.0.0.0"
PORT = 9000
BUFFER_SIZE = 4096
# numero de workers usados pelas funcoes paralelas da componente 1
DEFAULT_WORKERS = 4


# HANDLERS DOS METODOS RPC


def _rpc_find_max_prime(timeout: int) -> int:
    """
    Procura o maior numero primo possivel dentro de `timeout` segundos.

    Delega na versao paralela da componente 1 usando DEFAULT_WORKERS processos.

    params:
        timeout: tempo maximo em segundos (>= 1).

    Returns:
        Maior primo encontrado.
    """
    if not isinstance(timeout, int) or timeout < 1:
        raise ValueError("'timeout' deve ser um inteiro >= 1.")
    # find_max_prime_parallel devolve (primo, candidatos_testados);
    # o cliente so precisa do primo.
    result, _ = find_max_prime_parallel(timeout, DEFAULT_WORKERS)
    return result


def _rpc_is_prime(n: int) -> bool:
    """
    Verifica se n e primo.

    params:
        n: numero a verificar.

    Returns:
        True se n for primo, False caso contrario.
    """
    if not isinstance(n, int):
        raise ValueError("'n' deve ser um inteiro.")
    return is_prime(n)


def _rpc_game_of_life(grid: list, generations: int) -> list:
    """
    Simula o Game of Life durante `generations` geracoes.

    params:
        grid: grelha inicial (lista de listas de 0/1).
        generations: numero de geracoes a simular (>= 1).

    Returns:
        Estado da grelha apos as geracoes simuladas.
    """
    if not isinstance(grid, list) or len(grid) == 0:
        raise ValueError("'grid' deve ser uma lista nao vazia.")
    if not all(isinstance(row, list) for row in grid):
        raise ValueError("'grid' deve ser uma lista de listas.")
    cols = len(grid[0])
    for row in grid:
        if len(row) != cols:
            raise ValueError("todas as linhas da grelha devem ter o mesmo comprimento.")
        if not all(cell in (0, 1) for cell in row):
            raise ValueError("as celulas da grelha devem ser 0 ou 1.")
    if not isinstance(generations, int) or generations < 1:
        raise ValueError("'generations' deve ser um inteiro >= 1.")
    return game_of_life_parallel(grid, generations, DEFAULT_WORKERS)


def _rpc_list_methods() -> list:
    """
    Lista todas as operacoes disponiveis neste servidor RPC.

    Usa introspeccao (inspect) para extrair automaticamente o nome,
    parametros e descricao de cada metodo registado em METHODS.

    Returns:
        Lista de dicionarios com 'name', 'params' e 'description'.
    """
    methods = []
    for name, func in METHODS.items():
        sig = inspect.signature(func)
        params = []
        for p, param in sig.parameters.items():
            ann = param.annotation
            # annotation pode ser um tipo simples ou um alias genericos como list[list[int]]
            # hasattr protege contra AttributeError em aliases genericos
            type_str = ann.__name__ if hasattr(ann, "__name__") else str(ann)
            params.append({"name": p, "type": type_str})
        doc = inspect.getdoc(func) or ""
        description = doc.split("\n")[0].strip()
        methods.append({"name": name, "params": params, "description": description})
    return methods


# dicionario central de metodos disponiveis
# adicionar um novo metodo e so acrescentar uma entrada aqui
METHODS = {
    "find_max_prime": _rpc_find_max_prime,
    "is_prime":       _rpc_is_prime,
    "game_of_life":   _rpc_game_of_life,
    "list_methods":   _rpc_list_methods,
}


# LOGICA DE PEDIDO / RESPOSTA


def handle_request(raw: str) -> dict:
    """
    Processa uma mensagem JSON recebida e devolve a resposta como dicionario.

    Passos:
      1. Tenta deserializar o JSON.
      2. Verifica campos obrigatorios (method, params).
      3. Verifica se o metodo existe.
      4. Verifica parametros esperados vs recebidos.
      5. Invoca o handler e devolve o resultado.

    params:
        raw: string JSON recebida do cliente.

    Returns:
        {"result": valor} em caso de sucesso, {"error": msg} em caso de erro.
    """
    # passo 1: deserializar
    try:
        request = json.loads(raw)
    except json.JSONDecodeError as e:
        return {"error": f"JSON invalido: {e}"}

    # passo 2: validar estrutura basica
    if not isinstance(request, dict):
        return {"error": "o pedido deve ser um objecto JSON."}
    if "method" not in request:
        return {"error": "campo 'method' em falta."}
    if "params" not in request:
        return {"error": "campo 'params' em falta."}
    if not isinstance(request["params"], dict):
        return {"error": "campo 'params' deve ser um objecto JSON."}

    method_name = request["method"]
    params      = request["params"]

    # passo 3: verificar se o metodo existe
    if method_name not in METHODS:
        return {"error": f"metodo '{method_name}' nao existe. disponiveis: {list(METHODS.keys())}"}

    # passo 4: validar parametros
    func     = METHODS[method_name]
    expected = list(inspect.signature(func).parameters.keys())
    missing  = [p for p in expected if p not in params]
    if missing:
        return {"error": f"parametros em falta: {missing}"}
    extra = [p for p in params if p not in expected]
    if extra:
        return {"error": f"parametros desconhecidos: {extra}"}

    # passo 5: invocar o handler
    try:
        result = func(**params)
        return {"result": result}
    except (ValueError, TypeError) as e:
        return {"error": f"erro de validacao: {e}"}
    except Exception as e:
        return {"error": f"erro interno: {e}"}


# TRATAMENTO DE CLIENTES


def handle_client(conn: socket.socket, addr: tuple) -> None:
    """
    Trata a ligacao de um cliente individual.

    Corre numa thread dedicada. Le pedidos linha a linha, processa cada um
    e envia a resposta correspondente ate o cliente fechar a ligacao.

    params:
        conn: socket da ligacao com o cliente.
        addr: endereco (ip, porto) do cliente.
    """
    print(f"[+] cliente ligado: {addr[0]}:{addr[1]}")
    buffer = ""

    try:
        while True:
            try:
                data = conn.recv(BUFFER_SIZE)
            except OSError:
                break

            if not data:
                # cliente fechou a ligacao
                break

            # acumular no buffer -> uma mensagem pode chegar fragmentada em TCP
            buffer += data.decode("utf-8")

            # processar todas as mensagens completas (terminadas em '\n')
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if not line:
                    continue

                response      = handle_request(line)
                response_json = json.dumps(response, ensure_ascii=False) + "\n"

                try:
                    conn.sendall(response_json.encode("utf-8"))
                except BrokenPipeError:
                    return

    finally:
        conn.close()
        print(f"[-] cliente desligado: {addr[0]}:{addr[1]}")


# SERVIDOR PRINCIPAL


def start_server(host: str = HOST, port: int = PORT) -> None:
    """
    Inicia o servidor RPC e fica a aguardar ligacoes.

    Para cada cliente aceite, lanca uma thread daemon que trata a ligacao
    de forma concorrente sem bloquear o ciclo principal de aceitacao.

    params:
        host: endereco de escuta.
        port: porto de escuta.
    """
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # SO_REUSEADDR evita "Address already in use" ao reiniciar o servidor rapidamente
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    server_socket.bind((host, port))
    server_socket.listen()

    print(f"servidor RPC a escutar em {host}:{port}")
    print(f"metodos disponiveis: {list(METHODS.keys())}")
    print("aguardar ligacoes... (Ctrl+C para terminar)\n")

    try:
        while True:
            conn, addr = server_socket.accept()

            # daemon=True: a thread termina automaticamente quando o processo
            # principal terminar, sem necessidade de join explicito
            client_thread = threading.Thread(
                target=handle_client,
                args=(conn, addr),
                daemon=True,
            )
            client_thread.start()

    except KeyboardInterrupt:
        print("\nservidor a terminar...")
    finally:
        server_socket.close()
        print("servidor terminado.")


if __name__ == "__main__":
    # uso: python servidor.py        -> porta 9000 (por omissao)
    #      python servidor.py 9001   -> porta 9001
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    start_server(host=HOST, port=port)