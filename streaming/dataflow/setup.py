# Empacota o modulo `pipeline` para os workers do Dataflow (--setup_file).
# As dependencias do Beam ja vem na imagem padrao dos workers.
import setuptools

setuptools.setup(
    name="anac-stream-pipeline",
    version="2.0.0",
    packages=setuptools.find_packages(include=["pipeline", "pipeline.*"]),
)
