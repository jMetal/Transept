CONDA_ENV := transept
RUN := conda run --no-capture-output -n $(CONDA_ENV)
JAR_NAME := transept-core-0.1.0-jar-with-dependencies.jar

.PHONY: setup env jar lint format test run

# Creates the Conda environment (Python and Java) and puts the core jar in lib/.
#   make setup                 uses a jar built in a sibling clone of Transept-core
#   make setup JAR=<path>      copies the given jar
setup: env jar

env:
	conda env create -n $(CONDA_ENV) -f environment.yml || conda env update -n $(CONDA_ENV) -f environment.yml

jar:
	@mkdir -p lib
	@if [ -n "$(JAR)" ]; then \
	  cp "$(JAR)" lib/$(JAR_NAME) && echo "Copied $(JAR) to lib/$(JAR_NAME)"; \
	elif [ -f lib/$(JAR_NAME) ]; then \
	  echo "lib/$(JAR_NAME) is in place"; \
	else \
	  for candidate in ../transept-core ../Transept-core; do \
	    if [ -f $$candidate/target/$(JAR_NAME) ]; then \
	      cp $$candidate/target/$(JAR_NAME) lib/ && echo "Copied $$candidate/target/$(JAR_NAME) to lib/"; \
	      exit 0; \
	    fi; \
	  done; \
	  echo "No jar found: build it in a clone of Transept-core (mvn clean package -DskipTests)"; \
	  echo "and run 'make setup JAR=<path to $(JAR_NAME)>', or set its path in the app."; \
	  exit 1; \
	fi

lint:
	$(RUN) ruff check .

format:
	$(RUN) ruff format .

test:
	$(RUN) pytest tests/ -x

run:
	$(RUN) streamlit run app.py
