"""Which algorithms accept each formulation of --objectives."""

import dataclasses

from transept import options, runner


class TestObjectives:
    def test_should_offer_only_the_single_objective_algorithms_for_one_objective(self):
        assert options.algorithms_for("LDDT") == [
            "GENETIC_ALGORITHM",
            "ASYNC_GENETIC_ALGORITHM",
            "RANDOM_SEARCH",
            "RANDOM_SEEDED",
        ]

    def test_should_offer_the_multiobjective_algorithms_for_two_and_three(self):
        two = options.algorithms_for("SOPWTP_LDDT")
        assert two == options.algorithms_for("SOPWTP_LDDT_COVERAGE")
        assert "NSGA_II" in two and "MOEA_D" in two
        assert "GENETIC_ALGORITHM" not in two

    def test_should_reject_unsuitable_algorithms_and_moead_sizes(self):
        # Arrange
        request = runner.RunRequest(dataset="toy", seeds=("a", "b"), run_id="r", seed=1)

        # Act
        wrong_algorithm = runner.validate(
            dataclasses.replace(request, algorithm="GENETIC_ALGORITHM")
        )
        wrong_size = runner.validate(
            dataclasses.replace(
                request,
                algorithm="MOEA_D",
                objectives="SOPWTP_LDDT_COVERAGE",
                population_size=50,
            )
        )
        good = runner.validate(
            dataclasses.replace(request, algorithm="GENETIC_ALGORITHM", objectives="LDDT")
        )

        # Assert
        assert any("does not accept" in message for message in wrong_algorithm)
        assert any("MOEA/D with three objectives" in message for message in wrong_size)
        assert good == []

    def test_should_pass_the_objectives_to_the_tool(self, tmp_path):
        request = runner.RunRequest(
            dataset="toy", seeds=("a", "b"), run_id="r", seed=1, objectives="LDDT"
        )
        arguments = runner.command(request, "/t.jar", "/data", tmp_path)
        assert arguments[arguments.index("--objectives") + 1] == "LDDT"


class TestFormulationFor:
    def test_should_prefer_the_default_formulation(self):
        assert options.formulation_for("NSGA_II") == options.DEFAULT_OBJECTIVES
        assert options.formulation_for("RANDOM_SEARCH") == options.DEFAULT_OBJECTIVES

    def test_should_take_the_one_a_single_objective_algorithm_accepts(self):
        assert options.formulation_for("GENETIC_ALGORITHM") == "LDDT"

    def test_should_always_offer_the_algorithm_in_its_formulation(self):
        for algorithm in options.ALGORITHMS:
            assert algorithm in options.algorithms_for(options.formulation_for(algorithm))


class TestRunsAtATime:
    def test_should_run_a_parallel_algorithm_one_after_another(self):
        assert options.is_parallel("NSGA_II")
        assert options.runs_at_a_time("NSGA_II", 10, 18) == 1

    def test_should_share_the_cores_otherwise(self):
        assert not options.is_parallel("PAES")
        assert options.runs_at_a_time("PAES", 10, 4) == 4
        assert options.runs_at_a_time("PAES", 3, 18) == 3
        assert options.runs_at_a_time("PAES", 1, 18) == 1
