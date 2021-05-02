from setuptools import setup


setup(
    name='pyhsi',
    version='0.1.0',
    description='Hyperspectral imaging library',
    url='https://github.com/rddunphy/pyHSI',
    author='R. David Dunphy',
    author_email='david.dunphy@strath.ac.uk',
    license='MIT',
    packages=['pyhsi'],
    install_requires=[
        'pip>=20.3',
        'opencv-python',
        'numpy',
        'pypylon',
        'spectral'
    ]
)
