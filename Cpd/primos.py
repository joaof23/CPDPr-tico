"""""""""
Implementação sequencial e paralela para a procura do maior número primo
possível dentro de um limite temporal.

Notas:

1) Porque usamos processos e não threads?
   Ver numeros primos e uma tarefa cpu-bound. Em Python, threads não
   costumam escalar bem neste tipo de problema devido ao GIL. O módulo
   multiprocessing cria subprocessos independentes, permitindo paralelismo 
   em múltiplos corees.



3) Qual é a ideia da nossa abordagem paralela?
   Em vez de dar a cada worker um conjunto fixo de números para sempre, usamos
   alocação dinâmica por blocos . Cada worker vai pedindo o próximo
   bloco disponível, testa os candidatos desse bloco e, no fim, volta a pedir
   mais trabalho enquanto houver tempo.

    reais vantagens desta abordagem:
   - balanceamento de carga mais justo;
   - assim existe menos risco de um worker ficar com trabalho "pior" que os outros;
   - funciona bem com timeout, porque o espaço de procura não precisa de ser
     conhecido à partida.

4) Porque testar apenas números ímpares?
   depois de tratar o caso do 2, faz sentido testar apenas ímpares. Isto reduz o número de
   candidatos contiunuado a respeitar o enuciado pois usamos is_prime

5) Descriçao da nossa sincronização?
   - Um Value partilhado guarda o melhor primo global encontrado até ao momento.
   - Outro Value guarda o número total de candidatos testados.
   - Um terceiro Value guarda o próximo início de bloco a atribuir.
   - Locks garantem que estas atualizações não criam race conditions.

6) Porque atualizar o melhor primo global só no fim de cada chunk?
   Se qualquer worker escrever no estado global a cada primo encontrado, haveria
   muito overhead de sincronização. Guardar um melhor primo local dentro do
   bloco e só depois tentar atualizar o global reduz contenção.
"""

import time
import multiprocessing
from typing import Tuple


def is_prime(n: int) -> bool:
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


# Tamanho do bloco de trabalho atribuído de cada vez a um worker.
#CHUNK MAIOR -> MENOS OVERHEAD -> WORKERS DEMORAM MAIS
CHUNK_SIZE = 100_000


def _make_odd(n: int) -> int:
    """
    Funçao aux  que ve se o  valor devolvido é ímpar.

    Se n já for ímpar, devolve-o. Se for par, devolve o ímpar seguinte.
    Funçao aux  ajuda a garantir que a pesquisa principal percorre apenas
    candidatos relevantes (todos os ímpares >= 3).
    """
    return n if n % 2 == 1 else n + 1


def find_max_prime_sequential(timeout: int) -> Tuple[int, int]:
    """
    Procura sequencialmente o maior número primo possível dentro de `timeout`
    segundos.

    passos:
      - Trata o caso do 2 como primo inicial conhecido.
      - depois testa apenas números ímpares: 3, 5, 7, 9, ...
      - Mantém sempre o maior primo encontrado até ao momento.
      - Conta quantos candidatos foram testados.
      - Pára imediatamente quando o tempo limite é atingido.

    params:
        timeout: tempo em ms.

    Returns:
        Tuplo (maior_primo_encontrado, candidatos_testados).


    """
    start = time.monotonic()

    # 2 é o menor e primeiro número primo.
    best_prime = 2
    tested = 0


    candidate = 3

    while time.monotonic() - start < timeout:
        tested += 1
        if is_prime(candidate):
            best_prime = candidate
        candidate += 2

    return best_prime, tested


def _prime_worker(
    timeout: int,
    start_time: float,
    next_chunk_start,
    best_prime,
    tested_count,
    chunk_lock,
    best_lock,
    tested_lock,
    chunk_size: int,
) -> None:
    """
     versão paralela

    O worker repete o seguinte ciclo enquanto houver tempo:
      1. Pede, de forma sincronizada, o próximo bloco de candidatos ímpares.
      2. Testa todos os números ímpares desse bloco.
      3. Conta quantos candidatos testou localmente.
      4. Guarda o melhor primo local encontrado nesse bloco.
      5. No fim do bloco, atualiza os contadores globais com locks.

    Porque existe um start_time comum passado pelo processo principal?
      Para que todos os workers usem exatamente a mesma referência temporal e
      parem de forma coordenada.

    Porque cada worker mantém variáveis locais primeiro?
      Porque operações locais são mais baratas do que tocar constantemente em
      memória partilhada protegida por locks.
    """
    local_best = 2
    local_tested_total = 0

    while True:
        if time.monotonic() - start_time >= timeout:
            break

        # reservar o próximo bloco ainda não atribuído.
        with chunk_lock:
            block_start = next_chunk_start.value
            next_chunk_start.value += 2 * chunk_size

        # Ajustamos o início para garantir que é ímpar.
        block_start = _make_odd(block_start)
        block_end = block_start + 2 * chunk_size

        block_best = local_best
        block_tested = 0

        # Testa apenas ímpares dentro do bloco reservado.
        candidate = block_start
        while candidate < block_end:
            if time.monotonic() - start_time >= timeout:
                break

            block_tested += 1
            if is_prime(candidate) and candidate > block_best:
                block_best = candidate

            candidate += 2

        local_tested_total += block_tested
        local_best = max(local_best, block_best)

        # Atualização do melhor primo global.
        if block_best > best_prime.value:
            with best_lock:
                if block_best > best_prime.value:
                    best_prime.value = block_best

    # Atualização final do número total de candidatos testados.
    # É feita uma vez por worker para reduzir contenção.
    with tested_lock:
        tested_count.value += local_tested_total


def find_max_prime_parallel(timeout: int, workers: int) -> Tuple[int, int]:
    """
    Procura paralelamente o maior número primo possível dentro de `timeout`
    segundos, usando `workers` processos.

    Como acontece:
      - Multiprocessing com processos independentes.
      - Divisão dinâmica do espaço de procura por blocos de candidatos ímpares.
      - Cada worker pede trabalho ao processo principal através de um contador
        partilhado.
      - Cada worker mantém um melhor primo local e só no fim do bloco tenta
        atualizar o melhor primo global.
      - A terminação acontece de forma coordenada usando o mesmo relógio base
        e verificações periódicas de timeout.

    params:
        timeout: tempo máximo de execução em segundos.
        workers: número de processos a criar.

    Returns:
        Tuplo (maior_primo_encontrado, candidatos_testados).

    Justificação do uso de processos:
        A tarefa é CPU-bound; processos permitem explorar vários cores reais.

    Justificação da divisão dinâmica:
        Como o problema termina por tempo e não por limite superior fixo, não faz
        sentido repartir à cabeça um intervalo que não sabemos qual será.
        A alocação dinâmica por chunks adapta-se naturalmente ao timeout.
    """
    if workers < 1:
        raise ValueError("workers deve ser >= 1")

    start_time = time.monotonic()

    # Estado global partilhado.
    # best_prime começa em 2 porque é o menor primo conhecido.
    best_prime = multiprocessing.Value("q", 2)

    # Número total de candidatos testados por todos os workers.
    tested_count = multiprocessing.Value("q", 0)

    # Próximo início de chunk a distribuir.
    # Começamos em 3 porque 2 já foi tratado.
    next_chunk_start = multiprocessing.Value("q", 3)

    # Locks separados tornam a intenção mais clara:
    # - chunk_lock protege a reserva do próximo bloco;
    # - best_lock protege a atualização do melhor primo global;
    # - tested_lock protege o acumulado total de candidatos testados.
    chunk_lock = multiprocessing.Lock()
    best_lock = multiprocessing.Lock()
    tested_lock = multiprocessing.Lock()

    processes = []
    for _ in range(workers):
        p = multiprocessing.Process(
            target=_prime_worker,
            args=(
                timeout,
                start_time,
                next_chunk_start,
                best_prime,
                tested_count,
                chunk_lock,
                best_lock,
                tested_lock,
                CHUNK_SIZE,
            ),
        )
        processes.append(p)
        p.start()

    # Espera coordenada pela conclusão de todos os workers.
    for p in processes:
        p.join()

    return best_prime.value, tested_count.value


if __name__ == "__main__":

    multiprocessing.freeze_support()

    TIMEOUT = 2
    WORKERS = min(4, multiprocessing.cpu_count())

    print("=== Demonstração de primos ===")
    print(f"Timeout: {TIMEOUT}s | Workers: {WORKERS}")

    t0 = time.monotonic()
    seq_prime, seq_tested = find_max_prime_sequential(TIMEOUT)
    t1 = time.monotonic()

    par_prime, par_tested = find_max_prime_parallel(TIMEOUT, WORKERS)
    t2 = time.monotonic()

    print(f"Sequencial -> primo={seq_prime}, testados={seq_tested:,}, tempo={t1-t0:.3f}s")
    print(f"Paralelo   -> primo={par_prime}, testados={par_tested:,}, tempo={t2-t1:.3f}s")
