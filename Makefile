CONDA_ENV := transept
RUN := conda run --no-capture-output -n $(CONDA_ENV)
# The core jar in lib/, under a name without version (Maven names it with its version)
JAR_NAME := transept-core.jar
# A clone of Transept-core next to this repository, if there is one
CORE ?= $(firstword $(wildcard ../Transept-core/pom.xml ../transept-core/pom.xml))
CORE_DIR := $(patsubst %/pom.xml,%,$(CORE))

.PHONY: setup env jar core image image-multiarch run-image lint format test run

# Creates the Conda environment (Python, Java and Maven) and puts the core jar in lib/.
#   make setup                 builds the jar from a clone of Transept-core next to this one
#   make setup JAR=<path>      copies the given jar instead
#   make core                  rebuilds the jar (e.g. after a git pull in Transept-core)
setup: env jar

env:
	conda env create -n $(CONDA_ENV) -f environment.yml || conda env update -n $(CONDA_ENV) -f environment.yml

jar:
	@mkdir -p lib
	@if [ -n "$(JAR)" ]; then \
	  cp "$(JAR)" lib/$(JAR_NAME) && echo "Copied $(JAR) to lib/$(JAR_NAME)"; \
	elif [ -f lib/$(JAR_NAME) ]; then \
	  echo "lib/$(JAR_NAME) is in place ('make core' rebuilds it)"; \
	elif [ -n "$(CORE_DIR)" ]; then \
	  $(MAKE) --no-print-directory core; \
	else \
	  echo "No jar found. Clone Transept-core next to this repository and run 'make setup' again:"; \
	  echo "  git clone https://github.com/jMetal/Transept-core.git ../Transept-core"; \
	  echo "or run 'make setup JAR=<path to transept-core-<version>-jar-with-dependencies.jar>'."; \
	  exit 1; \
	fi

core:
	@if [ -z "$(CORE_DIR)" ]; then \
	  echo "No clone of Transept-core next to this repository (../Transept-core)."; exit 1; \
	fi
	@echo "Building the jar in $(CORE_DIR) (a few minutes the first time)..."
	$(RUN) mvn -q -f $(CORE_DIR)/pom.xml clean package -DskipTests
	@mkdir -p lib
	@built="$$(ls -t $(CORE_DIR)/target/transept-core-*-jar-with-dependencies.jar | head -1)"; \
	  cp "$$built" lib/$(JAR_NAME) && echo "Copied $$built to lib/$(JAR_NAME)"

# Builds the Docker image from the jar of a clone of Transept-core next to this repository.
image: core
	docker build -t transept .

# The same image for Intel and ARM machines (linux/amd64 and linux/arm64), e.g. before publishing it.
# The other architecture is emulated, so it takes longer. Keeping both locally needs the containerd
# image store of Docker (the default in recent Docker Desktop).
PLATFORMS ?= linux/amd64,linux/arm64
image-multiarch: core
	docker buildx build --platform $(PLATFORMS) -t transept --load .

# Runs the image built with `make image`; the runs and datasets stay in the transept-data volume.
run-image:
	docker run --rm -p 127.0.0.1:8501:8501 -v transept-data:/data transept

lint:
	$(RUN) ruff check .

format:
	$(RUN) ruff format .

test:
	$(RUN) pytest tests/ -x

run:
	$(RUN) streamlit run app.py
