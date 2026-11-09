# Transept with everything it needs: Python, Java and the jar of Transept core.
#
# The jar must be in lib/ first: `make image` builds it and then this image.
FROM eclipse-temurin:21-jre AS java

FROM python:3.11-slim
ENV JAVA_HOME=/opt/java/openjdk
# On the PATH too, so that the command line of Transept core can be used inside the container.
ENV PATH="$JAVA_HOME/bin:$PATH"
COPY --from=java /opt/java/openjdk /opt/java/openjdk

# tini reaps the detached runs: a run that ended must not look alive to Transept.
RUN apt-get update && apt-get install -y --no-install-recommends tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
COPY transept/ transept/
RUN pip install --no-cache-dir -e .

COPY app.py LICENSE README.md ./
COPY .streamlit/ .streamlit/
COPY pages/ pages/
COPY docs/ docs/
COPY examples/ examples/
# A fixed name, because the settings in the volume can outlive this image.
COPY lib/transept-core-*-jar-with-dependencies.jar lib/transept-core.jar

# Runs, datasets and settings live in the volume, not in the image.
ENV TRANSEPT_HOME=/data TRANSEPT_CORE_JAR=/app/lib/transept-core.jar
RUN useradd --create-home transept && mkdir /data && chown transept /data
USER transept
VOLUME /data

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD \
    python -c "import urllib.request as u; u.urlopen('http://localhost:8501/_stcore/health')"
# Inside the container it listens on every interface: `docker run -p 127.0.0.1:8501:8501` decides
# who can reach it, and that command only publishes the port on the machine of the user.
ENTRYPOINT ["tini", "--"]
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.headless=true"]
