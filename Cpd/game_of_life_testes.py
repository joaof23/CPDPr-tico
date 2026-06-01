"""
testes.py
=========
Conjunto de testes automáticos para validar as componentes do trabalho:
  - números primos;
  - Game of Life.

Os testes procuram validar:
  - correção funcional das funções base;
  - consistência entre versões sequencial e paralela;
  - alguns padrões clássicos do Game of Life.

Nota importante sobre multiprocessing:
  Os testes da versão paralela devem correr dentro de
  `if __name__ == "__main__":` para evitar problemas em Windows com spawn.
"""

import multiprocessing
from primos import is_prime, find_max_prime_sequential, find_max_prime_parallel
from game_of_life import game_of_life_sequential, game_of_life_parallel

PASS = " PASS"
FAIL = " FAIL"
resultados = []


def check(nome, condicao, detalhe=""):
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


def testar_sequencial_primos():
    print()
    print("=" * 60)
    print("TESTES: find_max_prime_sequential")
    print("=" * 60)

    primo, testados = find_max_prime_sequential(1)
    check("Resultado sequencial é primo", is_prime(primo), f"resultado={primo}")
    check("Candidatos testados > 0", testados > 0, f"testados={testados:,}")
    check("Retorna tuplo (int, int)", isinstance(primo, int) and isinstance(testados, int))

    primo_1s, _ = find_max_prime_sequential(1)
    primo_2s, _ = find_max_prime_sequential(2)
    check("Mais tempo -> primo maior ou igual", primo_2s >= primo_1s, f"1s={primo_1s}, 2s={primo_2s}")


def testar_paralelo_primos(num_workers):
    print()
    print("=" * 60)
    print(f"TESTES: find_max_prime_parallel (workers={num_workers})")
    print("=" * 60)

    primo_p, testados_p = find_max_prime_parallel(2, num_workers)
    check("Resultado paralelo é primo", is_prime(primo_p), f"resultado={primo_p}")
    check("Candidatos testados paralelo > 0", testados_p > 0, f"testados={testados_p:,}")
    check("Retorna tuplo (int, int)", isinstance(primo_p, int) and isinstance(testados_p, int))

    primo_1w, testados_1w = find_max_prime_parallel(2, 1)
    check("Paralelo com 1 worker devolve primo válido", is_prime(primo_1w), f"primo={primo_1w}")

    if num_workers >= 4:
        _, testados_4w = find_max_prime_parallel(2, 4)
        check("4 workers testam mais candidatos que 1", testados_4w > testados_1w,
              f"1 worker={testados_1w:,}, 4 workers={testados_4w:,}")

    primo_seq, _ = find_max_prime_sequential(3)
    primo_par, _ = find_max_prime_parallel(3, num_workers)
    check("Paralelo >= Sequencial no mesmo tempo [tendência]", primo_par >= primo_seq,
          f"paralelo={primo_par}, sequencial={primo_seq}")


# ============================================================
# TESTES: GAME OF LIFE
# ============================================================

def testar_game_of_life_base():
    print()
    print("=" * 60)
    print("TESTES: Game of Life - regras base")
    print("=" * 60)

    # Grelha vazia continua vazia.
    empty = [
        [0, 0, 0],
        [0, 0, 0],
        [0, 0, 0],
    ]
    expected_empty = [
        [0, 0, 0],
        [0, 0, 0],
        [0, 0, 0],
    ]
    result_empty = game_of_life_sequential(empty, 1)
    check("Grelha vazia mantém-se vazia", result_empty == expected_empty)

    # Still life clássico: block. Deve permanecer igual ao longo do tempo.
    block = [
        [0, 0, 0, 0],
        [0, 1, 1, 0],
        [0, 1, 1, 0],
        [0, 0, 0, 0],
    ]
    result_block = game_of_life_sequential(block, 5)
    check("Block é estável (still life)", result_block == block)

    # Oscilador clássico: blinker (período 2).
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
    result_blinker_1 = game_of_life_sequential(blinker_vertical, 1)
    result_blinker_2 = game_of_life_sequential(blinker_vertical, 2)
    check("Blinker após 1 geração muda de vertical para horizontal", result_blinker_1 == blinker_horizontal)
    check("Blinker após 2 gerações volta ao estado inicial", result_blinker_2 == blinker_vertical)

    # Zero gerações -> estado inalterado.
    original = [
        [0, 1, 0],
        [1, 1, 0],
        [0, 0, 1],
    ]
    result_zero = game_of_life_sequential(original, 0)
    check("0 gerações devolve a mesma grelha", result_zero == original)


def testar_game_of_life_glider():
    print()
    print("=" * 60)
    print("TESTES: Game of Life - glider")
    print("=" * 60)

    # O glider é um padrão famoso com período 4; ao fim de 4 gerações,
    # reaparece deslocado uma célula na diagonal [Game of Life references].
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

    result_after_4 = game_of_life_sequential(initial, 4)
    check("Glider após 4 gerações desloca-se na diagonal", result_after_4 == expected_after_4)


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

    seq_0 = game_of_life_sequential(grid, 0)
    par_0 = game_of_life_parallel(grid, 0, num_workers)
    check("Paralelo == Sequencial para 0 gerações", par_0 == seq_0)

    seq_1 = game_of_life_sequential(grid, 1)
    par_1 = game_of_life_parallel(grid, 1, num_workers)
    check("Paralelo == Sequencial para 1 geração", par_1 == seq_1)

    seq_5 = game_of_life_sequential(grid, 5)
    par_5 = game_of_life_parallel(grid, 5, num_workers)
    check("Paralelo == Sequencial para 5 gerações", par_5 == seq_5)

    seq_10 = game_of_life_sequential(grid, 10)
    par_10 = game_of_life_parallel(grid, 10, num_workers)
    check("Paralelo == Sequencial para 10 gerações", par_10 == seq_10)

    par_1w = game_of_life_parallel(grid, 5, 1)
    check("Paralelo com 1 worker coincide com sequencial", par_1w == seq_5)


def testar_game_of_life_erros(num_workers):
    print()
    print("=" * 60)
    print("TESTES: Game of Life - validação de erros")
    print("=" * 60)

    try:
        game_of_life_sequential([[0, 1], [1]], 1)
        check("Deteta linhas com tamanhos diferentes", False)
    except ValueError:
        check("Deteta linhas com tamanhos diferentes", True)

    try:
        game_of_life_sequential([[0, 2], [1, 0]], 1)
        check("Deteta células diferentes de 0/1", False)
    except ValueError:
        check("Deteta células diferentes de 0/1", True)

    try:
        game_of_life_parallel([[0, 1], [1, 0]], -1, num_workers)
        check("Deteta generations negativo", False)
    except ValueError:
        check("Deteta generations negativo", True)

    try:
        game_of_life_parallel([[0, 1], [1, 0]], 1, 0)
        check("Deteta workers inválido", False)
    except ValueError:
        check("Deteta workers inválido", True)


# ============================================================
# RESUMO
# ============================================================

def resumo():
    print()
    print("=" * 60)
    total = len(resultados)
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
    testar_sequencial_primos()
    testar_paralelo_primos(NUM_WORKERS)

    testar_game_of_life_base()
    testar_game_of_life_glider()
    testar_game_of_life_parallel(NUM_WORKERS)
    testar_game_of_life_erros(NUM_WORKERS)

    resumo()