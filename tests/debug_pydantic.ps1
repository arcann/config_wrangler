poetry run pip uninstall pydantic
$Env:SKIP_CYTHON=1
poetry run pip install --no-cache-dir --no-binary :all: pydantic