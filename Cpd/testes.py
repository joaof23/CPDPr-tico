"""
testes.py
=========
Conjunto de testes automáticos para validar a componente dos números primos.

Este ficheiro foi escrito com foco em:
  - correção funcional;
  - compatibilidade com Windows + multiprocessing;
  - testes claros e fáceis de justificar no relatório.


"""

import multiprocessing
from primos import is_prime, find_max_prime_sequential, find_max_prime_parallel

PASS = " PASS"
FAIL = "FAILED"
resultados = []


def check(nome, condicao, detalhe=""):
    """
    Regista e imprime o resultado de um teste.

    params:
        nome: descrição humana do teste.
        condicao: resultado booleano do teste.
        detalhe: informação extra a mostrar no output.
    """
    estado = PASS if condicao else FAIL
    msg = f"{estado} | {nome}"
    if detalhe:
        msg += f"  ({detalhe})"
    print(msg)
    resultados.append((nome, condicao))


def testar_is_prime():
    """Testes de base para a função de primalidade obrigatória do enunciado."""
    print("=" * 60)
    print("TESTES: is_prime")
    print("=" * 60)

    # Casos básicos e edge cases.
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
    Testes da versão sequencial.

    O objetivo aqui não é forçar um primo exato, porque há pequenas variações
    de performance entre máquinas. Em vez disso, validamos propriedades que
    devem sempre ser verdadeiras.
    """
    print()
    print("=" * 60)
    print("TESTES: find_max_prime_sequential")
    print("=" * 60)

    primo, testados = find_max_prime_sequential(1)
    check("Resultado é primo", is_prime(primo), f"resultado={primo}")
    check("Candidatos testados > 0", testados > 0, f"testados={testados:,}")
    check("Retorna tuplo (int, int)", isinstance(primo, int) and isinstance(testados, int))

    primo_1s, _ = find_max_prime_sequential(1)
    primo_2s, _ = find_max_prime_sequential(2)
    check("Mais tempo -> primo maior ou igual", primo_2s >= primo_1s, f"1s={primo_1s}, 2s={primo_2s}")


def testar_paralelo(num_workers):
    """
    Testes da versão paralela.

    Estes testes devem correr apenas dentro do bloco principal, para evitar
    problemas do método spawn em Windows.
    """
    print()
    print("=" * 60)
    print(f"TESTES: find_max_prime_parallel (workers={num_workers})")
    print("=" * 60)

    primo_p, testados_p = find_max_prime_parallel(2, num_workers)
    check("Resultado paralelo é primo", is_prime(primo_p), f"resultado={primo_p}")
    check("Candidatos testados paralelo > 0", testados_p > 0, f"testados={testados_p:,}")
    check("Retorna tuplo (int, int)", isinstance(primo_p, int) and isinstance(testados_p, int))

    primo_1w, testados_1w = find_max_prime_parallel(2, 1)
    check("Paralelo 1 worker devolve primo válido", is_prime(primo_1w), f"primo={primo_1w}")

    if num_workers >= 4:
        _, testados_4w = find_max_prime_parallel(2, 4)
        check("4 workers testam mais candidatos que 1", testados_4w > testados_1w,
              f"1 worker={testados_1w:,}, 4 workers={testados_4w:,}")

    primo_seq, _ = find_max_prime_sequential(3)
    primo_par, _ = find_max_prime_parallel(3, num_workers)
    check("Paralelo >= Sequencial no mesmo tempo [tendência]", primo_par >= primo_seq,
          f"paralelo={primo_par}, sequencial={primo_seq}")


def resumo():
    """Imprime o resumo final de execução dos testes."""
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
    testar_sequencial()
    testar_paralelo(NUM_WORKERS)
    resumo()
