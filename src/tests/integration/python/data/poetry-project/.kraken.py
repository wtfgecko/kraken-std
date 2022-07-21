import os

from kraken.std import python

python.python_settings(always_use_managed_env=True).add_package_index(
    alias="local",
    index_url=os.environ["LOCAL_PACKAGE_INDEX"],
    # Need credentials, but they can be bogus, for unauthenticated Pypiserver
    credentials=("foo", "bar"),
)
python.install()
python.mypy()
python.publish(package_index="local", distributions=python.build().output_files)
