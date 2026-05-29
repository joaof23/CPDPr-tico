"""
primos.py
=========
Módulo para a procura do maior número primo possível dentro de um limite temporal.

Implementa:
  - is_prime(n)                              : verificação de primalidade (fornecida pelo enunciado)
  - find_max_prime_sequential(timeout)       : procura sequencial
  - find_max_prime_parallel(timeout, workers): procura paralela com múltiplos processos

Decisão de design:
  Usa multiprocessing (processos) e não threads, porque o problema é CPU-bound.
   o GIL  impede que threads executem código Python
  verdadeiramente em paralelo. Processos contornam o GIL e deixam acontecer o  paralelismo .
"""

import time
import multiprocessing


# funçao de verificar prime (fornecida pelo enunciado)


def is_prime(n: int) -> bool:
    """
    Verifica se um número inteiro é primo.

    Parâmetros:
        n (int): número a verificar.

    Retorna:
        bool: True se n é primo, False caso contrário.

    Nota:
        Esta função é fornecida pelo enunciado e não pode ser alterada.
        Usa o algoritmo de divisão por 6k +/- 1, mais eficiente do que
        testar todos os divisores até sqrt(n).
    """
    if n < 2:
        return False
    if n in (2, 3):
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False

    divisor = 5
    while divisor * divisor <= n:
        if n % divisor == 0 or n % (divisor + 2) == 0:
            return False
        divisor += 6

    return True



# VERSÃO SEQUENCIAL


def find_max_prime_sequential(timeout: int):
    """
    Procura o maior número primo possível durante, no máximo, `timeout` segundos,
    utilizando uma abordagem sequencial (single-thread, single-process).

    A implementação explora o espaço de procura de forma contínua, testando
    candidatos crescentes, até ao limite temporal.

    Parâmetros:
        timeout (int): tempo máximo de execução em segundos.

    Retorna:
        tuple(int, int): (maior primo encontrado, total de candidatos testados)
    """
    best_prime = 2
    candidate = 2
    candidates_tested = 0
    start = time.monotonic()

    while time.monotonic() - start < timeout:
        candidates_tested += 1
        if is_prime(candidate):
            best_prime = candidate
        candidate += 1

    return best_prime, candidates_tested



# VERSÃO PARALELA - função de cada worker


def _worker(start_candidate: int, step: int, timeout: float, start_time: float,
            best_value, lock, candidates_counter):
    """
    Função executada por cada processo worker na versão paralela.

    Cada worker testa candidatos numa progressão aritmética com passo `step`,
    começando em `start_candidate`. Esta estratégia garante divisão explícita
    e equilibrada do espaço de procura sem sobreposição entre workers.

    Exemplo com 4 workers:
        worker 0 testa: 2, 6, 10, 14, ...
        worker 1 testa: 3, 7, 11, 15, ...
        worker 2 testa: 4, 8, 12, 16, ...
        worker 3 testa: 5, 9, 13, 17, ...

    Parâmetros:
        start_candidate (int)  : primeiro candidato deste worker.
        step (int)             : passo entre candidatos (igual ao número de workers).
        timeout (float)        : tempo máximo em segundos.
        start_time (float)     : instante de início partilhado por todos os workers.
        best_value             : multiprocessing.Value partilhado para o melhor primo global.
        lock                   : multiprocessing.Lock para proteger escritas em best_value.
        candidates_counter     : multiprocessing.Value para contar candidatos testados no total.
    """
    candidate = start_candidate
    local_count = 0  # Contador local para minimizar acessos à memória partilhada

    while time.monotonic() - start_time < timeout:
        local_count += 1
        if is_prime(candidate):
            with lock:
                if candidate > best_value.value:
                    best_value.value = candidate
        candidate += step

    # Atualizar o contador global com o total deste worker (uma só escrita no fim)
    with lock:
        candidates_counter.value += local_count



# VERSÃO PARALELA - função principal


def find_max_prime_parallel(timeout: int, workers: int):
    """
    Procura o maior número primo possível durante, no máximo, `timeout` segundos,
    recorrendo à execução paralela de múltiplos processos (workers).

    Estratégia de divisão do espaço de procura:
        Os candidatos são distribuídos por interleaving (intercalação):
        worker i testa os candidatos 2+i, 2+i+workers, 2+i+2*workers, ...
        Isto garante cobertura completa, sem sobreposição e com carga equilibrada.

    Sincronização:
        O melhor primo global é guardado numa variável partilhada (multiprocessing.Value)
        protegida por um Lock, evitando race conditions.

    Terminação coordenada:
        Todos os workers terminam quando o tempo limite é atingido, verificando
        periodicamente o tempo decorrido.

    Parâmetros:
        timeout (int) : tempo máximo de execução em segundos.
        workers (int) : número de processos paralelos a utilizar.

    Retorna:
        tuple(int, int): (maior primo encontrado, total de candidatos testados)
    """
    best_value = multiprocessing.Value('l', 2)        # Melhor primo partilhado
    candidates_counter = multiprocessing.Value('l', 0) # Contador total de candidatos
    lock = multiprocessing.Lock()
    start_time = time.monotonic()

    processes = []
    for i in range(workers):
        p = multiprocessing.Process(
            target=_worker,
            args=(2 + i, workers, timeout, start_time, best_value, lock, candidates_counter)
        )
        processes.append(p)
        p.start()

    for p in processes:
        p.join()

    return best_value.value, candidates_counter.value



# BLOCO DE TESTE RÁPIDO (execução direta do ficheiro)


if __name__ == "__main__":
    TIMEOUT = 5

    print(f"=== Sequencial (timeout={TIMEOUT}s) ===")
    t0 = time.monotonic()
    primo_seq, testados_seq = find_max_prime_sequential(TIMEOUT)
    t1 = time.monotonic()
    print(f"Maior primo         : {primo_seq}")
    print(f"Nº de algarismos    : {len(str(primo_seq))}")
    print(f"Candidatos testados : {testados_seq:,}")
    print(f"Tempo de execução   : {t1 - t0:.2f}s")

    print()

    NUM_WORKERS = multiprocessing.cpu_count()
    print(f"=== Paralelo (timeout={TIMEOUT}s, workers={NUM_WORKERS}) ===")
    t2 = time.monotonic()
    primo_par, testados_par = find_max_prime_parallel(TIMEOUT, NUM_WORKERS)
    t3 = time.monotonic()
    print(f"Maior primo         : {primo_par}")
    print(f"Nº de algarismos    : {len(str(primo_par))}")
    print(f"Candidatos testados : {testados_par:,}")
    print(f"Tempo de execução   : {t3 - t2:.2f}s")

    print()
    ganhou = "MAIOR" if primo_par >= primo_seq else "menor"
    print(f"A versão paralela encontrou um primo {ganhou} do que a sequencial.")
    print(f"Candidatos testados pela paralela: {testados_par/testados_seq:.1f}x mais do que a sequencial.")