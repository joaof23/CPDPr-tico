"""
game_of_life.py
===============
Implementação sequencial e paralela do Conway's Game of Life.

Ideias principais da solução:

1) Double buffering
   Em cada geração lemos SEMPRE da grelha atual e escrevemos SEMPRE numa nova
   grelha. No fim da geração, trocamos as referências das duas grelhas.

   Porque isto é importante?
   Porque no Game of Life todas as células de uma geração têm de ser calculadas
   a partir do estado da geração anterior. Se atualizássemos a mesma grelha
   "no sítio", algumas células seriam calculadas com vizinhos já alterados e o
   resultado ficaria incorreto.



2) Cada worker fica responsável por um intervalo contíguo de linhas.

   Porque não dividir por células alternadas?
   Porque a memória da grelha está organizada por linhas. Trabalhar com regiões
   contíguas melhora localidade e reduz efeitos maus de cache. Vimos noutros jogos a recomendação de  dividir a grelha em regiões contíguas,alinhadas com a organização em memória.

3) Uma geração de cada vez, com barreira implícita no processo principal
   O processo principal cria os workers de uma geração, recolhe os resultados
   dessa geração e só depois passa à geração seguinte.

   Isto garante a sincronização entre gerações exigida pelo enunciado.
   ninguém pode começar a geração seguinte
   antes de todos acabarem a atual.

4) Gestão de fronteiras sem grelha cíclica
   O enunciado diz explicitamente que a grelha não é cíclica. Por isso, uma
   célula na fronteira tem menos vizinhos e qualquer acesso fora da grelha vale
   0 .

5) Comunicação simples e correta
   aqui aproveitamos que estamos no mesmo nó e
   passamos a grelha da geração atual a todos os workers como objeto apenas de
   leitura. Isto mantém a lógica correta das fronteiras entre regiões.

   continua a respeitar a ideia de dependência de fronteira
   descrita na literatura de halo exchange; simplesmente usamos uma solução mais
   adequada ao contexto do trabalho em Python com multiprocessing.
"""

import multiprocessing
from copy import deepcopy
from typing import List, Tuple

Grid = List[List[int]]


def _validate_grid(grid: Grid) -> None:
    """
    Valida a grelha de entrada.

    Regras assumidas :
      - a grelha é uma lista de listas;
      - todas as linhas têm o mesmo comprimento;
      - os valores das células são 0 ou 1.


    """
    if not isinstance(grid, list):
        raise TypeError("grid deve ser uma lista de listas")

    if len(grid) == 0:
        return

    if not all(isinstance(row, list) for row in grid):
        raise TypeError("grid deve ser uma lista de listas")

    cols = len(grid[0])
    for row in grid:
        if len(row) != cols:
            raise ValueError("todas as linhas da grid devem ter o mesmo tamanho")
        for cell in row:
            if cell not in (0, 1):
                raise ValueError("cada célula da grid deve ser 0 ou 1")


def _copy_grid(grid: Grid) -> Grid:
    """Cópia profunda simples da grelha."""
    return [row[:] for row in grid]


def _count_neighbors(grid: Grid, row: int, col: int, rows: int, cols: int) -> int:
    """
    Conta vizinhos vivos da célula.

    A grelha NÃO é cíclica. Logo, qualquer coordenada fora dos limites conta
    como célula morta.
    """
    live_neighbors = 0

    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue

            nr = row + dr
            nc = col + dc

            if 0 <= nr < rows and 0 <= nc < cols:
                live_neighbors += grid[nr][nc]

    return live_neighbors


def _next_cell_state(current_state: int, live_neighbors: int) -> int:
    """
    Aplica as regras do Game of Life a uma única célula.

    OQ E SUPOSTO :
      - viva com <2 vizinhos -> morre
      - viva com 2 ou 3 -> mantém-se viva
      - viva com >3 -> morre
      - morta com 3 -> nasce
      - caso contrário mantém o estado apropriado
    """
    if current_state == 1:
        if live_neighbors < 2:
            return 0
        if live_neighbors in (2, 3):
            return 1
        return 0

    return 1 if live_neighbors == 3 else 0


def game_of_life_sequential(grid: Grid, generations: int) -> Grid:
    """
    Simula o Game of Life de forma sequencial.

    Estratégia:
      - usa double buffering: current_grid -> next_grid;
      - calcula todas as células da geração seguinte com base apenas na geração
        atual;
      - no fim de cada geração troca as referências das grelhas.

    params:
        grid: grelha inicial.
        generations: número de gerações a simular.

    Returns:
        Nova grelha com o estado final após as gerações pedidas.
    """
    if generations < 0:
        raise ValueError("generations deve ser >= 0")

    _validate_grid(grid)

    if not grid:
        return []

    rows = len(grid)
    cols = len(grid[0])

    current_grid = _copy_grid(grid)

    for _ in range(generations):
        next_grid = [[0] * cols for _ in range(rows)]

        for r in range(rows):
            for c in range(cols):
                neighbors = _count_neighbors(current_grid, r, c, rows, cols)
                next_grid[r][c] = _next_cell_state(current_grid[r][c], neighbors)

        # Double buffering: passamos a ler da grelha acabada de calcular.
        current_grid = next_grid

    return current_grid


def _compute_row_chunk(
    current_grid: Grid,
    start_row: int,
    end_row: int,
    rows: int,
    cols: int,
    output_queue,
    chunk_index: int,
) -> None:
    """
    Worker que calcula uma fatia contígua de linhas para UMA geração.

    params:
        current_grid: grelha da geração atual (apenas leitura).
        start_row: primeira linha inclusiva da fatia.
        end_row: última linha exclusiva da fatia.
        rows, cols: dimensões da grelha.
        output_queue: fila para devolver resultados ao processo principal.
        chunk_index: índice do chunk para reordenar resultados depois.

    Porque devolvemos (chunk_index, start_row, partial_rows)?
      Porque processos podem terminar fora de ordem. Assim o processo principal
      consegue montar a grelha final da geração na ordem correta.
    """
    partial_rows = []

    for r in range(start_row, end_row):
        new_row = [0] * cols
        for c in range(cols):
            neighbors = _count_neighbors(current_grid, r, c, rows, cols)
            new_row[c] = _next_cell_state(current_grid[r][c], neighbors)
        partial_rows.append(new_row)

    output_queue.put((chunk_index, start_row, partial_rows))


def _split_rows(rows: int, workers: int) -> List[Tuple[int, int]]:
    """
    Divide a grelha em faixas de linhas aproximadamente equilibradas.

    Estratégia:
      - cada worker recebe um bloco contíguo de linhas;
      - se a divisão não for exata, os primeiros workers recebem 1 linha extra.

    Isto é melhor do que uma divisão aleatória porque:
      - mantém localidade em memória;
      - simplifica a gestão das fronteiras entre regiões;
      - tende a distribuir o trabalho de forma equilibrada.
    """
    workers = min(workers, rows) if rows > 0 else 1
    base = rows // workers
    extra = rows % workers

    ranges = []
    start = 0
    for i in range(workers):
        size = base + (1 if i < extra else 0)
        end = start + size
        ranges.append((start, end))
        start = end

    return ranges


def game_of_life_parallel(grid: Grid, generations: int, workers: int) -> Grid:
    """
    Simula o Game of Life recorrendo a múltiplos processos.

    Abordagem usada:
      - double buffering entre gerações;
      - divisão da grelha em regiões (faixas de linhas contíguas);
      - um conjunto de workers calcula em paralelo partes da geração seguinte;
      - o processo principal recolhe todos os resultados, recompõe a grelha e só
        então inicia a geração seguinte.

    Isto implementa explicitamente os pontos pedidos no enunciado:
      - divisão da grelha em regiões;
      - execução paralela de múltiplos workers;
      - correta gestão das fronteiras entre regiões;
      - sincronização entre gerações;
      - consistência dos resultados face à versão sequencial.

    params:
        grid: grelha inicial (lista de listas de 0/1).
        generations: número de gerações.
        workers: número de processos.

    Returns:
        Estado final da grelha.
    """
    if generations < 0:
        raise ValueError("generations deve ser >= 0")
    if workers < 1:
        raise ValueError("workers deve ser >= 1")

    _validate_grid(grid)

    if not grid:
        return []

    rows = len(grid)
    cols = len(grid[0])

    # Se houver apenas um worker, usar a implementação sequencial evita o
    # overhead de criar processos sem qualquer benefício real.
    if workers == 1:
        return game_of_life_sequential(grid, generations)

    current_grid = _copy_grid(grid)
    row_chunks = _split_rows(rows, workers)

    for _ in range(generations):
        output_queue = multiprocessing.Queue()
        processes = []

        # Lançamos um processo por chunk de linhas nesta geração.
        # Esta é uma barreira implícita por geração: só avançamos quando todos
        # os resultados tiverem sido recolhidos.
        for chunk_index, (start_row, end_row) in enumerate(row_chunks):
            p = multiprocessing.Process(
                target=_compute_row_chunk,
                args=(
                    current_grid,
                    start_row,
                    end_row,
                    rows,
                    cols,
                    output_queue,
                    chunk_index,
                ),
            )
            processes.append(p)
            p.start()

        # Recolhemos as fatias produzidas em qualquer ordem.
        collected = [None] * len(row_chunks)
        for _ in row_chunks:
            chunk_index, start_row, partial_rows = output_queue.get()
            collected[chunk_index] = (start_row, partial_rows)

        for p in processes:
            p.join()

        next_grid = [[0] * cols for _ in range(rows)]
        for item in collected:
            start_row, partial_rows = item
            for offset, row_data in enumerate(partial_rows):
                next_grid[start_row + offset] = row_data

        current_grid = next_grid

    return current_grid


if __name__ == "__main__":
    multiprocessing.freeze_support()

    # Pequena demonstração com o padrão "blinker".
    initial = [
        [0, 0, 0, 0, 0],
        [0, 0, 1, 0, 0],
        [0, 0, 1, 0, 0],
        [0, 0, 1, 0, 0],
        [0, 0, 0, 0, 0],
    ]

    generations = 1
    workers = min(4, multiprocessing.cpu_count())

    seq = game_of_life_sequential(initial, generations)
    par = game_of_life_parallel(initial, generations, workers)

    print("Sequencial:")
    for row in seq:
        print(row)

    print("Paralelo:")
    for row in par:
        print(row)

    print("Resultados iguais:", seq == par)