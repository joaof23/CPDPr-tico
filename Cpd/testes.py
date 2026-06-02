"""
testes.py
=========
Conjunto de testes automaticos para validar as componentes do trabalho:
  - numeros primos;
  - Game of Life;
  - Servidor RPC (requer servidor em execucao em localhost:9000).

Execucao:
  python testes.py            -> todos os testes (RPC ignorado se servidor offline)
  python testes.py --no-rpc   -> salta testes RPC mesmo que o servidor esteja online

Nota importante sobre multiprocessing:
  Os testes da versao paralela devem correr dentro de
  `if __name__ == "__main__":` para evitar problemas em Windows com spawn.
"""

import multiprocessing
import socket
import json
import sys
from primos import is_prime, find_max_prime_sequential, find_max_prime_parallel
from game_of_life import game_of_life_sequential, game_of_life_parallel

PASS = " PASS"
FAIL = "FAILED"
resultados = []


def check(nome, condicao, detalhe=""):
    """
    Regista e imprime o resultado de um teste.

    params:
        nome: descricao humana do teste.
        condicao: resultado booleano do teste.
        detalhe: informacao extra a mostrar no output.
    """
    estado = PASS if condicao else FAIL
    msg = f"{estado} | {nome}"
    if detalhe:
        msg += f"  ({detalhe})"
    print(msg)
    resultados.append((nome, condicao))


# ============================================================
# TESTES: PRIMOS
# ============================================================

def testar_is_prime():
    """Testes de base para a funcao de primalidade obrigatoria do enunciado."""
    print("=" * 60)
    print("TESTES: is_prime")
    print("=" * 60)

    check("is_prime(0) == False", is_prime(0) == False)
    check("is_prime(1) == False", is_prime(1) == False)
    check("is_prime(2) == True", is_prime(2) == True)
    check("is_prime(3) == True", is_prime(3) == True)
    check("is_prime(4) == False", is_prime(4) == False)
    check("is_prime(5) == True", is_prime(5) == True)
    check("is_prime(9) == False", is_prime(9) == False, "9 = 3x3")
    check("is_prime(11) == True", is_prime(11) == True)
    check("is_prime(13) == True", is_prime(13) == True)
    check("is_prime(15) == False", is_prime(15) == False, "15 = 3x5")
    check("is_prime(17) == True", is_prime(17) == True)
    check("is_prime(25) == False", is_prime(25) == False, "25 = 5x5")
    check("is_prime(97) == True", is_prime(97) == True)
    check("is_prime(-1) == False", is_prime(-1) == False)
    check("is_prime(-7) == False", is_prime(-7) == False)
    check("is_prime(7919) == True", is_prime(7919) == True, "1000o primo")
    check("is_prime(7920) == False", is_prime(7920) == False, "composto")
    check("is_prime(104729) == True", is_prime(104729) == True, "10000o primo")


def testar_sequencial():
    """
    Testes da versao sequencial.

    Nao forcamos um primo exato porque ha variacoes de performance entre
    maquinas. Validamos propriedades que devem ser sempre verdadeiras.
    """
    print()
    print("=" * 60)
    print("TESTES: find_max_prime_sequential")
    print("=" * 60)

    primo, testados = find_max_prime_sequential(1)
    check("Resultado e primo", is_prime(primo), f"resultado={primo}")
    check("Candidatos testados > 0", testados > 0, f"testados={testados:,}")
    check("Retorna tuplo (int, int)", isinstance(primo, int) and isinstance(testados, int))

    primo_1s, _ = find_max_prime_sequential(1)
    primo_2s, _ = find_max_prime_sequential(2)
    check("Mais tempo -> primo maior ou igual", primo_2s >= primo_1s, f"1s={primo_1s}, 2s={primo_2s}")


def testar_paralelo(num_workers):
    """
    Testes da versao paralela.

    Estes testes devem correr apenas dentro do bloco principal, para evitar
    problemas do metodo spawn em Windows.
    """
    print()
    print("=" * 60)
    print(f"TESTES: find_max_prime_parallel (workers={num_workers})")
    print("=" * 60)

    primo_p, testados_p = find_max_prime_parallel(2, num_workers)
    check("Resultado paralelo e primo", is_prime(primo_p), f"resultado={primo_p}")
    check("Candidatos testados paralelo > 0", testados_p > 0, f"testados={testados_p:,}")
    check("Retorna tuplo (int, int)", isinstance(primo_p, int) and isinstance(testados_p, int))

    primo_1w, testados_1w = find_max_prime_parallel(2, 1)
    check("Paralelo 1 worker devolve primo valido", is_prime(primo_1w), f"primo={primo_1w}")

    if num_workers >= 4:
        _, testados_4w = find_max_prime_parallel(2, 4)
        check("4 workers testam mais candidatos que 1", testados_4w > testados_1w,
              f"1 worker={testados_1w:,}, 4 workers={testados_4w:,}")

    primo_seq, _ = find_max_prime_sequential(3)
    primo_par, _ = find_max_prime_parallel(3, num_workers)
    check("Paralelo >= Sequencial no mesmo tempo [tendencia]", primo_par >= primo_seq,
          f"paralelo={primo_par}, sequencial={primo_seq}")


# ============================================================
# TESTES: GAME OF LIFE
# ============================================================

def testar_game_of_life_base():
    print()
    print("=" * 60)
    print("TESTES: Game of Life - regras base")
    print("=" * 60)

    # grelha vazia continua vazia
    empty = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
    check("Grelha vazia mantem-se vazia", game_of_life_sequential(empty, 1) == empty)

    # still life classico: block. deve permanecer igual ao longo do tempo
    block = [
        [0, 0, 0, 0],
        [0, 1, 1, 0],
        [0, 1, 1, 0],
        [0, 0, 0, 0],
    ]
    check("Block e estavel (still life)", game_of_life_sequential(block, 5) == block)

    # oscilador classico: blinker (periodo 2)
    blinker_vertical = [
        [0, 0, 0, 0, 0],
        [0, 0, 1, 0, 0],
        [0, 0, 1, 0, 0],
        [0, 0, 1, 0, 0],
        [0, 0, 0, 0, 0],
    ]
    blinker_horizontal = [
        [0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0],
        [0, 1, 1, 1, 0],
        [0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0],
    ]
    check("Blinker apos 1 geracao muda de vertical para horizontal",
          game_of_life_sequential(blinker_vertical, 1) == blinker_horizontal)
    check("Blinker apos 2 geracoes volta ao estado inicial",
          game_of_life_sequential(blinker_vertical, 2) == blinker_vertical)

    # zero geracoes -> estado inalterado
    original = [[0, 1, 0], [1, 1, 0], [0, 0, 1]]
    check("0 geracoes devolve a mesma grelha",
          game_of_life_sequential(original, 0) == original)


def testar_game_of_life_glider():
    print()
    print("=" * 60)
    print("TESTES: Game of Life - glider")
    print("=" * 60)

    # o glider tem periodo 4; ao fim de 4 geracoes reaparece deslocado na diagonal
    initial = [
        [0, 1, 0, 0, 0],
        [0, 0, 1, 0, 0],
        [1, 1, 1, 0, 0],
        [0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0],
    ]
    expected_after_4 = [
        [0, 0, 0, 0, 0],
        [0, 0, 1, 0, 0],
        [0, 0, 0, 1, 0],
        [0, 1, 1, 1, 0],
        [0, 0, 0, 0, 0],
    ]
    check("Glider apos 4 geracoes desloca-se na diagonal",
          game_of_life_sequential(initial, 4) == expected_after_4)


def testar_game_of_life_parallel(num_workers):
    print()
    print("=" * 60)
    print(f"TESTES: Game of Life paralelo (workers={num_workers})")
    print("=" * 60)

    grid = [
        [0, 1, 0, 0, 0, 0],
        [0, 0, 1, 0, 0, 0],
        [1, 1, 1, 0, 0, 0],
        [0, 0, 0, 1, 1, 0],
        [0, 0, 0, 1, 1, 0],
        [0, 0, 0, 0, 0, 0],
    ]

    for gens in [0, 1, 5, 10]:
        seq = game_of_life_sequential(grid, gens)
        par = game_of_life_parallel(grid, gens, num_workers)
        check(f"Paralelo == Sequencial para {gens} geracoes", par == seq)

    seq_5 = game_of_life_sequential(grid, 5)
    check("Paralelo com 1 worker coincide com sequencial",
          game_of_life_parallel(grid, 5, 1) == seq_5)


def testar_game_of_life_erros(num_workers):
    print()
    print("=" * 60)
    print("TESTES: Game of Life - validacao de erros")
    print("=" * 60)

    try:
        game_of_life_sequential([[0, 1], [1]], 1)
        check("Deteta linhas com tamanhos diferentes", False)
    except ValueError:
        check("Deteta linhas com tamanhos diferentes", True)

    try:
        game_of_life_sequential([[0, 2], [1, 0]], 1)
        check("Deteta celulas diferentes de 0/1", False)
    except ValueError:
        check("Deteta celulas diferentes de 0/1", True)

    try:
        game_of_life_parallel([[0, 1], [1, 0]], -1, num_workers)
        check("Deteta generations negativo", False)
    except ValueError:
        check("Deteta generations negativo", True)

    try:
        game_of_life_parallel([[0, 1], [1, 0]], 1, 0)
        check("Deteta workers invalido", False)
    except ValueError:
        check("Deteta workers invalido", True)


# ============================================================
# TESTES: SERVIDOR RPC
# ============================================================

RPC_HOST = "127.0.0.1"
RPC_PORT = 9000
SKIP_RPC = "--no-rpc" in sys.argv


def _server_available() -> bool:
    """Tenta ligar ao servidor para verificar se esta acessivel."""
    if SKIP_RPC:
        return False
    try:
        s = socket.create_connection((RPC_HOST, RPC_PORT), timeout=1)
        s.close()
        return True
    except OSError:
        return False


def _rpc_call(method: str, params: dict) -> dict:
    """
    Envia um pedido RPC ao servidor e devolve a resposta deserializada.

    params:
        method: nome do metodo a invocar.
        params: dicionario de parametros.

    Returns:
        Dicionario {"result": ...} ou {"error": ...}.
    """
    s       = socket.create_connection((RPC_HOST, RPC_PORT), timeout=30)
    request = json.dumps({"method": method, "params": params}) + "\n"
    s.sendall(request.encode("utf-8"))

    # acumular ate '\n' pelo mesmo motivo que no servidor: fragmentacao TCP
    raw = ""
    while "\n" not in raw:
        chunk = s.recv(65536)
        if not chunk:
            break
        raw += chunk.decode("utf-8")
    s.close()
    return json.loads(raw.split("\n")[0])


def testar_rpc():
    print()
    print("=" * 60)
    print("TESTES: Servidor RPC")
    print("=" * 60)

    # list_methods
    resp = _rpc_call("list_methods", {})
    check("list_methods retorna result", "result" in resp)
    check("list_methods retorna lista", isinstance(resp.get("result"), list))
    names = {m["name"] for m in resp.get("result", [])}
    for op in ["find_max_prime", "is_prime", "game_of_life", "list_methods"]:
        check(f"list_methods inclui '{op}'", op in names)
    for m in resp.get("result", []):
        check(f"metodo '{m.get('name')}' tem 'params' e 'description'",
              "params" in m and "description" in m)

    # is_prime
    resp = _rpc_call("is_prime", {"n": 97})
    check("is_prime(97) == True", resp.get("result") is True)
    resp = _rpc_call("is_prime", {"n": 100})
    check("is_prime(100) == False", resp.get("result") is False)
    resp = _rpc_call("is_prime", {"n": 1})
    check("is_prime(1) == False", resp.get("result") is False)

    # find_max_prime
    resp = _rpc_call("find_max_prime", {"timeout": 2})
    check("find_max_prime retorna primo valido",
          "result" in resp and is_prime(resp["result"]),
          f"resultado={resp.get('result')}")

    # game_of_life
    block = [[0,0,0,0],[0,1,1,0],[0,1,1,0],[0,0,0,0]]
    resp  = _rpc_call("game_of_life", {"grid": block, "generations": 5})
    check("game_of_life block estavel", resp.get("result") == block)

    blinker_v = [[0,0,0,0,0],[0,0,1,0,0],[0,0,1,0,0],[0,0,1,0,0],[0,0,0,0,0]]
    resp      = _rpc_call("game_of_life", {"grid": blinker_v, "generations": 2})
    check("game_of_life blinker periodo 2", resp.get("result") == blinker_v)

    # tratamento de erros
    resp = _rpc_call("nao_existe", {})
    check("Metodo inexistente retorna error", "error" in resp)

    resp = _rpc_call("is_prime", {})
    check("Parametro em falta retorna error", "error" in resp)

    resp = _rpc_call("is_prime", {"n": 7, "extra": 999})
    check("Parametro extra retorna error", "error" in resp)

    # JSON invalido enviado directamente pelo socket
    s = socket.create_connection((RPC_HOST, RPC_PORT), timeout=5)
    s.sendall(b"isto nao e json\n")
    raw = ""
    while "\n" not in raw:
        chunk = s.recv(4096)
        if not chunk:
            break
        raw += chunk.decode("utf-8")
    s.close()
    resp = json.loads(raw.split("\n")[0])
    check("JSON invalido retorna error", "error" in resp)

    # multiplas ligacoes simultaneas
    import threading
    results_mt = []
    errors_mt  = []

    def call_is_prime():
        try:
            r = _rpc_call("is_prime", {"n": 7})
            results_mt.append(r.get("result"))
        except Exception as e:
            errors_mt.append(str(e))

    threads = [threading.Thread(target=call_is_prime) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    check("Sem erros em 5 ligacoes simultaneas", len(errors_mt) == 0,
          f"erros={errors_mt}")
    check("5 ligacoes simultaneas devolvem True para is_prime(7)",
          all(r is True for r in results_mt))


# ============================================================
# RESUMO
# ============================================================

def resumo():
    """Imprime o resumo final de execucao dos testes."""
    print()
    print("=" * 60)
    total  = len(resultados)
    passou = sum(1 for _, ok in resultados if ok)
    falhou = total - passou
    print(f"RESUMO: {passou}/{total} testes passaram  |  {falhou} falharam")
    print("=" * 60)

    if falhou > 0:
        print("Testes com falha:")
        for nome, ok in resultados:
            if not ok:
                print(f"  {FAIL} {nome}")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    NUM_WORKERS = min(4, multiprocessing.cpu_count())

    testar_is_prime()
    testar_sequencial()
    testar_paralelo(NUM_WORKERS)

    testar_game_of_life_base()
    testar_game_of_life_glider()
    testar_game_of_life_parallel(NUM_WORKERS)
    testar_game_of_life_erros(NUM_WORKERS)

    if _server_available():
        print(f"\nservidor RPC detectado em {RPC_HOST}:{RPC_PORT} -- a correr testes RPC...")
        testar_rpc()
    else:
        print(f"\nservidor RPC nao detectado em {RPC_HOST}:{RPC_PORT} -- testes RPC ignorados.")
        print("para correr os testes RPC, inicie o servidor e volte a executar este ficheiro.")

    resumo()
