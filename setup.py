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
    scripts=['PyHSI'],
    install_requires=[
        'numpy>=1.19',
        'opencv-python>=4.4',
        'pip>=20.3',
        'pypylon>=1.7',
        'pyserial>=3.5',
        'spectral>=0.22',
        'PySimpleGUI>=4.41',
        'matplotlib>=3.4'
    ]
)
