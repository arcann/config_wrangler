poetry install --with=docs
sphinx-build -b html -E -N -w issues.log source build