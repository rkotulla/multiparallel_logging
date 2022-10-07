
from setuptools import setup, find_namespace_packages

# with open("README.rst", "rb") as f: # 
#     long_descr = f.read().decode("utf-8")

setup(
    name = "multiparlog",
    package_dir = {'': 'src'},
    packages = ['multiparlog'],
    # packages = find_namespace_packages(include=['src.multiparlog.*']),
    # entry_points = {
    #     "console_scripts": []
    #     },
    version = "1.0.0",
    # description = "A flexible multi-processing safe logging tool",
    # # long_description = long_descr,
    # author = "Ralf Kotulla",
    # author_email = "ralf.kotulla@gmail.com",
    # url = "https://github.com/rkotulla/multiparallel_logging",
    )
