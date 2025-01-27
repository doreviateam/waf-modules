from setuptools import setup, find_packages

setup(
    name="watergile_localization_iso",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        'pytest',
        'pytest-odoo',
        'pytest-cov',
    ],
)