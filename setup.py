from setuptools import setup

# Per https://ianhopkinson.org.uk/2022/02/understanding-setup-py-setup-cfg-and-pyproject-toml-in-python/
# a minimal setup.py file to get other tools happy with the pyproject.toml
#
# If you are looking for a way to bump versions in code, this is now handled
# at GitHub tag time via mechanisms specified in the pyproject.toml file.

if __name__ == "__main__":
    setup()
