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
    "SOPWTP_LDDT": ("SOPwTP and lDDT (published)", 2),
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
MUTATIONS = ("TM_SAFE_GAP_SHIFT", "MERGE_GAP_RUNS", "RANDOM_CHOICE")

STEADY_STATE = ("SMS_EMOA", "MOEA_D", "PAES")

DESCRIPTIONS = {
    "NSGA_II": "NSGA-II, the published configuration",
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
}

DEFAULT_MAX_EVALUATIONS = 10_000
DEFAULT_POPULATION_SIZE = 100
DEFAULT_CROSSOVER_PROBABILITY = 0.8
DEFAULT_MUTATION_PROBABILITY = 0.2
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


def default_mutation_probability(algorithm: str) -> float:
    """Returns the mutation probability the CLI uses when none is given."""
    return PAES_MUTATION_PROBABILITY if algorithm == "PAES" else DEFAULT_MUTATION_PROBABILITY
