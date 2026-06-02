"""
cliente.py
==========
Cliente RPC que comunica com o servidor via sockets TCP.

Permite invocar interactivamente as operacoes disponibilizadas pelo servidor:
  - find_max_prime(timeout)
  - is_prime(n)
  - game_of_life(grid, generations)
  - list_methods()

Notas:

1) Porque uma ligacao persistente em vez de uma por pedido?
   Manter o socket aberto durante toda a sessao evita o overhead de
   estabelecer uma nova ligacao TCP para cada operacao. Para um cliente
   interactivo isto e mais eficiente e mais simples de gerir.

2) Como e feita a leitura da resposta?
   As respostas podem chegar fragmentadas em varios pacotes TCP.
   Acumulamos os dados num buffer ate encontrar '\n' que marca o fim
   da mensagem, igual ao que o servidor faz do lado oposto.

3) O que acontece se a ligacao cair a meio?
   O cliente tenta reconectar automaticamente antes de mostrar o erro.
   Se a reconexao falhar, o programa termina com mensagem clara.

4) Como usar:
   python cliente.py                    -> liga a localhost:9000
   python cliente.py 192.168.1.10       -> liga a host especifico
   python cliente.py 192.168.1.10 9001  -> liga a host e porto especificos
"""

import socket
import json
import sys

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9000
# buffer maior para respostas com grelhas grandes
BUFFER_SIZE  = 65536


# CAMADA DE COMUNICACAO


def connect(host: str, port: int) -> socket.socket:
    """
    Estabelece uma ligacao TCP ao servidor RPC.

    params:
        host: endereco do servidor.
        port: porto do servidor.

    Returns:
        Socket ligado ao servidor.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        return sock
    except ConnectionRefusedError:
        print(f"[ERRO] nao foi possivel ligar a {host}:{port}.")
        print("       certifique-se de que o servidor esta em execucao.")
        sys.exit(1)
    except OSError as e:
        print(f"[ERRO] falha de rede: {e}")
        sys.exit(1)


def send_request(sock: socket.socket, method: str, params: dict) -> dict:
    """
    Envia um pedido JSON ao servidor e aguarda a resposta.

    params:
        sock: socket ligado ao servidor.
        method: nome da operacao a invocar.
        params: dicionario de parametros da operacao.

    Returns:
        Resposta deserializada {"result": ...} ou {"error": ...}.
    """
    request = {"method": method, "params": params}
    message = json.dumps(request, ensure_ascii=False) + "\n"

    try:
        sock.sendall(message.encode("utf-8"))
    except BrokenPipeError:
        raise RuntimeError("ligacao ao servidor perdida ao enviar o pedido.")

    # acumular ate encontrar '\n' -> a resposta pode chegar em fragmentos TCP
    raw = ""
    while "\n" not in raw:
        try:
            chunk = sock.recv(BUFFER_SIZE)
        except OSError as e:
            raise RuntimeError(f"erro ao receber resposta: {e}")
        if not chunk:
            raise RuntimeError("o servidor fechou a ligacao inesperadamente.")
        raw += chunk.decode("utf-8")

    try:
        return json.loads(raw.split("\n")[0].strip())
    except json.JSONDecodeError as e:
        raise RuntimeError(f"resposta invalida do servidor: {e}")


# APRESENTACAO DE RESULTADOS


def _print_grid(grid: list) -> None:
    """
    Mostra uma grelha do Game of Life no terminal.

    Celulas vivas sao representadas por '#', mortas por '.'.

    params:
        grid: grelha a mostrar.
    """
    for row in grid:
        print("  " + " ".join("#" if cell else "." for cell in row))


def print_result(method: str, response: dict) -> None:
    """
    Apresenta a resposta do servidor de forma legivel.

    params:
        method: nome do metodo invocado.
        response: resposta do servidor.
    """
    if "error" in response:
        print(f"\n[ERRO DO SERVIDOR] {response['error']}")
        return

    result = response["result"]
    print()

    if method == "list_methods":
        print("operacoes disponiveis no servidor:")
        print("-" * 50)
        for m in result:
            params_str = ", ".join(f"{p['name']}: {p['type']}" for p in m["params"])
            print(f"  {m['name']}({params_str})")
            print(f"    -> {m['description']}")
        print("-" * 50)

    elif method == "is_prime":
        print(f"resultado: {'e primo' if result else 'nao e primo'}")

    elif method == "find_max_prime":
        print(f"maior primo encontrado : {result}")
        print(f"numero de algarismos   : {len(str(result))}")

    elif method == "game_of_life":
        rows  = len(result)
        cols  = len(result[0]) if rows > 0 else 0
        alive = sum(cell for row in result for cell in row)
        print(f"grelha final ({rows}x{cols}) -- celulas vivas: {alive}")
        # so mostrar a grelha se for pequena o suficiente para o terminal
        if rows <= 40 and cols <= 60:
            _print_grid(result)
        else:
            print("  (grelha demasiado grande para visualizacao -- apenas estatisticas)")

    else:
        print(f"resultado: {result}")


# LEITURA DE PARAMETROS


def _read_int(prompt: str, min_val: int = None) -> int:
    """
    Le um inteiro do stdin, repetindo em caso de entrada invalida.

    params:
        prompt: mensagem a mostrar ao utilizador.
        min_val: valor minimo aceitavel (opcional).

    Returns:
        Inteiro introduzido pelo utilizador.
    """
    while True:
        try:
            value = int(input(prompt).strip())
            if min_val is not None and value < min_val:
                print(f"  o valor deve ser >= {min_val}. tente novamente.")
                continue
            return value
        except ValueError:
            print("  entrada invalida. introduza um numero inteiro.")


def _read_grid() -> list:
    """
    Le uma grelha do Game of Life do stdin.

    Dois modos:
      1. Geracao aleatoria (dimensoes + densidade).
      2. Introducao manual linha a linha (ex: "0 1 0 1 1").

    Returns:
        Grelha introduzida pelo utilizador (lista de listas de 0/1).
    """
    print("\n  como pretende definir a grelha?")
    print("    [1] gerar aleatoriamente")
    print("    [2] introduzir manualmente")

    choice = input("  opcao: ").strip()

    if choice == "1":
        rows = _read_int("  numero de linhas    : ", min_val=1)
        cols = _read_int("  numero de colunas   : ", min_val=1)
        while True:
            try:
                density = float(input("  densidade (0.0-1.0) [0.3]: ").strip() or "0.3")
                if 0.0 <= density <= 1.0:
                    break
                print("  a densidade deve estar entre 0.0 e 1.0.")
            except ValueError:
                print("  entrada invalida.")

        import random
        grid  = [[1 if random.random() < density else 0 for _ in range(cols)] for _ in range(rows)]
        alive = sum(cell for row in grid for cell in row)
        print(f"  grelha {rows}x{cols} gerada -- {alive} celulas vivas.")
        return grid

    else:
        print("  introduza a grelha linha a linha (celulas separadas por espacos: 0 ou 1).")
        print("  linha vazia para terminar.")
        grid          = []
        expected_cols = None

        while True:
            raw = input(f"  linha {len(grid)}: ").strip()
            if raw == "":
                if len(grid) == 0:
                    print("  a grelha deve ter pelo menos uma linha.")
                    continue
                break
            try:
                row = [int(x) for x in raw.split()]
            except ValueError:
                print("  introduza apenas 0s e 1s separados por espacos.")
                continue
            if not all(c in (0, 1) for c in row):
                print("  as celulas devem ser 0 ou 1.")
                continue
            if expected_cols is None:
                expected_cols = len(row)
            elif len(row) != expected_cols:
                print(f"  todas as linhas devem ter {expected_cols} colunas.")
                continue
            grid.append(row)

        return grid


# MENU INTERACTIVO


MENU = """
+==============================================+
|         cliente RPC -- menu                  |
+==============================================+
|  [1]  listar operacoes disponiveis           |
|  [2]  verificar se n e primo                 |
|  [3]  encontrar o maior primo                |
|  [4]  simular game of life                   |
|  [0]  sair                                   |
+==============================================+
"""


def menu_list_methods(sock: socket.socket) -> None:
    """Invoca list_methods() no servidor e mostra o resultado."""
    response = send_request(sock, "list_methods", {})
    print_result("list_methods", response)


def menu_is_prime(sock: socket.socket) -> None:
    """Le n, invoca is_prime(n) e mostra o resultado."""
    n        = _read_int("\n  introduza o numero a verificar: ")
    response = send_request(sock, "is_prime", {"n": n})
    print_result("is_prime", response)


def menu_find_max_prime(sock: socket.socket) -> None:
    """Le o timeout, invoca find_max_prime(timeout) e mostra o resultado."""
    timeout  = _read_int("\n  tempo limite em segundos (>= 1): ", min_val=1)
    print(f"  a procurar o maior primo durante {timeout}s (aguarde)...")
    response = send_request(sock, "find_max_prime", {"timeout": timeout})
    print_result("find_max_prime", response)


def menu_game_of_life(sock: socket.socket) -> None:
    """Le a grelha e geracoes, invoca game_of_life() e mostra o resultado."""
    grid        = _read_grid()
    generations = _read_int("\n  numero de geracoes (>= 1): ", min_val=1)
    print("  a enviar pedido ao servidor (aguarde)...")
    response    = send_request(sock, "game_of_life", {"grid": grid, "generations": generations})
    print_result("game_of_life", response)


# mapa de opcoes do menu
ACTIONS = {
    "1": menu_list_methods,
    "2": menu_is_prime,
    "3": menu_find_max_prime,
    "4": menu_game_of_life,
}


def run_client(host: str, port: int) -> None:
    """
    Ponto de entrada do cliente interactivo.

    Estabelece ligacao ao servidor e entra num ciclo de menu ate o utilizador
    sair (opcao 0) ou premir Ctrl+C. Em caso de falha de comunicacao, tenta
    reconectar antes de desistir.

    params:
        host: endereco do servidor.
        port: porto do servidor.
    """
    print(f"\na ligar a {host}:{port}...")
    sock = connect(host, port)
    print(f"ligado ao servidor RPC em {host}:{port}.")

    try:
        while True:
            print(MENU)
            choice = input("opcao: ").strip()

            if choice == "0":
                print("a terminar o cliente. ate logo!")
                break
            elif choice in ACTIONS:
                try:
                    ACTIONS[choice](sock)
                except RuntimeError as e:
                    print(f"\n[ERRO DE COMUNICACAO] {e}")
                    print("a tentar reconectar...")
                    try:
                        sock.close()
                        sock = connect(host, port)
                        print("reconectado com sucesso.")
                    except SystemExit:
                        break
            else:
                print("  opcao invalida. escolha entre 0 e 4.")

    except KeyboardInterrupt:
        print("\n\ninterrompido pelo utilizador.")
    finally:
        sock.close()


if __name__ == "__main__":
    # uso: python cliente.py                   -> localhost:9000
    #      python cliente.py 192.168.1.10      -> host especifico, porta 9000
    #      python cliente.py 192.168.1.10 9001 -> host e porta especificos
    host = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HOST
    port = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_PORT
    run_client(host, port)