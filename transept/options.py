"""The options of the `run` command that Transept offers, mirroring Transept core's CLI."""

ALGORITHMS = (
    "NSGA_II",
    "ASYNC_NSGA_II",
    "SPEA2",
    "NSGA_III",
    "AGE_MOEA",
    "AGE_MOEA_II",
    "SMS_EMOA",
    "MOEA_D",
    "PAES",
    "GENETIC_ALGORITHM",
    "ASYNC_GENETIC_ALGORITHM",
    "RANDOM_SEARCH",
    "RANDOM_SEEDED",
)
# Algorithms of the tool that Transept does not offer.
NOT_OFFERED: tuple[str, ...] = ()

# Formulations of --objectives, their description and number of objectives.
OBJECTIVES = {
    "SOPWTP_LDDT": ("SOPwTP and lDDT", 2),
    "LDDT": ("lDDT only (single objective)", 1),
    "SOPWTP_LDDT_COVERAGE": ("SOPwTP, lDDT and coverage (experimental)", 3),
}
DEFAULT_OBJECTIVES = "SOPWTP_LDDT"

# Objectives each algorithm accepts, as the `algorithms` command of the tool reports them.
SINGLE_OBJECTIVE = ("GENETIC_ALGORITHM", "ASYNC_GENETIC_ALGORITHM")
RANDOM_SEARCHES = ("RANDOM_SEARCH", "RANDOM_SEEDED")
MAX_OBJECTIVES = 3

# Asynchronous algorithms: all threads stay busy, but runs with several threads do not repeat.
ASYNCHRONOUS = ("ASYNC_NSGA_II", "ASYNC_GENETIC_ALGORITHM")

# Population sizes with weight vectors for MOEA/D with three objectives.
MOEAD_THREE_OBJECTIVE_SIZES = (91, 100, 136, 300, 500, 600, 800, 1000, 1200)
MUTATIONS = (
    "TM_SAFE_GAP_SHIFT",
    "MERGE_GAP_RUNS",
    "RANDOM_CHOICE",
    "TM_SAFE_BLOCK_SHIFT",
    "TM_SAFE_WINDOW_REALIGN",
)
CROSSOVERS = ("TM_SAFE_SINGLE_POINT", "TM_SAFE_UNIFORM")
DEFAULT_CROSSOVER = "TM_SAFE_SINGLE_POINT"

STEADY_STATE = ("SMS_EMOA", "MOEA_D", "PAES")

# Mutations that move gap runs at random, which --max-shift limits.
SHIFTING_MUTATIONS = ("TM_SAFE_GAP_SHIFT", "RANDOM_CHOICE")
# Algorithms that do not use the crossover, or that ignore the operators altogether.
WITHOUT_CROSSOVER = ("PAES", "RANDOM_SEARCH", "RANDOM_SEEDED")
WITHOUT_OPERATORS = ("RANDOM_SEARCH",)

# What the parameters of the operators mean, for their widgets.
PARAMETER_HELP = {
    "maxShift": "Largest number of columns a gap run can move at once; 0 means no limit.",
    "cutCandidates": "Valid cuts drawn per crossover, of which the one that adds the fewest gaps "
    "is used; 1 means a cut at random.",
    "blockShift": "Largest number of columns a block of gaps shared by several rows can move.",
    "realignWindow": "Number of columns of the window in which one row is realigned.",
    "algorithmResult": "What the algorithm returns: its final population, or an external archive "
    "that keeps the best solutions found during the whole run.",
    "archiveType": "With an external archive: bounded by crowding distance, or unbounded.",
    "populationSizeWithArchive": "Population size when an external archive is used.",
    "mutation": "Mutation operator; every one keeps the transmembrane helices whole.",
    "crossover": "Crossover operator; neither cuts a transmembrane helix.",
    "selection": "How the parents are chosen.",
}

DESCRIPTIONS = {
    "NSGA_II": "NSGA-II, the default algorithm",
    "ASYNC_NSGA_II": "NSGA-II, asynchronous (keeps all threads busy)",
    "SPEA2": "SPEA2 (strength ranking, nearest-neighbour density)",
    "GENETIC_ALGORITHM": "Genetic algorithm, generational",
    "ASYNC_GENETIC_ALGORITHM": "Genetic algorithm, asynchronous (keeps all threads busy)",
    "NSGA_III": "NSGA-III (population size multiple of 4)",
    "AGE_MOEA": "AGE-MOEA",
    "AGE_MOEA_II": "AGE-MOEA-II",
    "SMS_EMOA": "SMS-EMOA (steady state: threads do not help)",
    "MOEA_D": "MOEA/D (steady state: threads do not help)",
    "PAES": "PAES, (1+1) with a crowding-distance archive; mutation only",
    "RANDOM_SEARCH": "Random search, gaps at random (weak sanity check)",
    "RANDOM_SEEDED": "Random search from the seeds (strong sanity check)",
    "TM_SAFE_GAP_SHIFT": "Gap shift that never breaks a transmembrane helix",
    "MERGE_GAP_RUNS": "Joins two consecutive gap runs of a row",
    "RANDOM_CHOICE": "TM_SAFE_GAP_SHIFT or MERGE_GAP_RUNS, chosen at random",
    "TM_SAFE_BLOCK_SHIFT": "Moves a block of gaps shared by several rows one column",
    "TM_SAFE_WINDOW_REALIGN": "Realigns one row inside a window of 50 columns",
    "TM_SAFE_SINGLE_POINT": "Single point, at a column that cuts no helix",
    "TM_SAFE_UNIFORM": "Uniform, between the columns where both parents agree; adds no gap",
}

DEFAULT_MAX_EVALUATIONS = 10_000
DEFAULT_POPULATION_SIZE = 100
DEFAULT_CROSSOVER_PROBABILITY = 0.8
DEFAULT_MUTATION_PROBABILITY = 0.2
DEFAULT_MAX_SHIFT = 0
DEFAULT_CUT_CANDIDATES = 1
MAX_SHIFT_LIMIT = 200
CUT_CANDIDATES_LIMIT = 64
PAES_MUTATION_PROBABILITY = 1.0


def objective_range(algorithm: str) -> tuple[int, int]:
    """Returns the smallest and largest number of objectives an algorithm accepts."""
    if algorithm in SINGLE_OBJECTIVE:
        return 1, 1
    return (1 if algorithm in RANDOM_SEARCHES else 2), MAX_OBJECTIVES


def algorithms_for(objectives: str) -> list[str]:
    """Returns the algorithms that accept a formulation of --objectives, in the tool's order."""
    count = OBJECTIVES[objectives][1]
    return [
        algorithm
        for algorithm in ALGORITHMS
        if objective_range(algorithm)[0] <= count <= objective_range(algorithm)[1]
    ]


def formulation_for(algorithm: str) -> str:
    """Returns the default formulation if the algorithm accepts it, else the first it accepts."""
    low, high = objective_range(algorithm)
    if low <= OBJECTIVES[DEFAULT_OBJECTIVES][1] <= high:
        return DEFAULT_OBJECTIVES
    return next(name for name, (_, count) in OBJECTIVES.items() if low <= count <= high)


def is_parallel(algorithm: str) -> bool:
    """Tells whether several evaluation threads speed an algorithm up."""
    return algorithm not in STEADY_STATE


def runs_at_a_time(algorithm: str, runs: int, cores: int) -> int:
    """Returns how many independent runs of an algorithm to keep active.

    A parallel algorithm already uses its threads, so its runs go one after another; the others
    cannot use them, so their runs share the cores.
    """
    return 1 if is_parallel(algorithm) else max(1, min(runs, cores))


def default_mutation_probability(algorithm: str) -> float:
    """Returns the mutation probability the CLI uses when none is given."""
    return PAES_MUTATION_PROBABILITY if algorithm == "PAES" else DEFAULT_MUTATION_PROBABILITY
