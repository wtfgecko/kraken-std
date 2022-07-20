# ::requirements kraken-std>=0.1.11

from kraken.std.python import black, flake8, isort, mypy, pytest, build, python_settings, publish, install

black()
flake8()
isort()
mypy()
pytest()
install()

python_settings().add_package_index("test-pypi", "https://test.pypi.org", None)
publish("pythonPublish", "test-pypi", build().output_files)
