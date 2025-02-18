from setuptools import setup


setup(
    name='gbgpu',
    url='https://github.com/NataliaKor/GBGPU',
    classifiers=[
      'Development Status :: 3 - Alpha',
      'Intended Audience :: Science/Research',
      'Programming Language :: Python :: 3',
    ],
    packages=setuptools.find_packages(),
    install_requires=['numpy', 'cupy']
)
