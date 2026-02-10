|Icon| |title|_
===============

.. |title| replace:: pdfbl.sequential
.. _title: https://pdf-bl.github.io/pdfbl.sequential

.. |Icon| image:: https://avatars.githubusercontent.com/pdf-bl
        :target: https://pdf-bl.github.io/pdfbl.sequential
        :height: 100px

|PyPI| |Forge| |PythonVersion| |PR|

|CI| |Codecov| |Black| |Tracking|

.. |Black| image:: https://img.shields.io/badge/code_style-black-black
        :target: https://github.com/psf/black

.. |CI| image:: https://github.com/pdf-bl/pdfbl.sequential/actions/workflows/matrix-and-codecov-on-merge-to-main.yml/badge.svg
        :target: https://github.com/pdf-bl/pdfbl.sequential/actions/workflows/matrix-and-codecov-on-merge-to-main.yml

.. |Codecov| image:: https://codecov.io/gh/pdf-bl/pdfbl.sequential/branch/main/graph/badge.svg
        :target: https://codecov.io/gh/pdf-bl/pdfbl.sequential

.. |Forge| image:: https://img.shields.io/conda/vn/conda-forge/pdfbl.sequential
        :target: https://anaconda.org/conda-forge/pdfbl.sequential

.. |PR| image:: https://img.shields.io/badge/PR-Welcome-29ab47ff
        :target: https://github.com/pdf-bl/pdfbl.sequential/pulls

.. |PyPI| image:: https://img.shields.io/pypi/v/pdfbl.sequential
        :target: https://pypi.org/project/pdfbl.sequential/

.. |PythonVersion| image:: https://img.shields.io/pypi/pyversions/pdfbl.sequential
        :target: https://pypi.org/project/pdfbl.sequential/

.. |Tracking| image:: https://img.shields.io/badge/issue_tracking-github-blue
        :target: https://github.com/pdf-bl/pdfbl.sequential/issues

Automated sequential refinements of PDF data

Scripts for running sequential PDF refinements using diffpy.cmi automatically

For more information about the pdfbl.sequential library, please consult our `online documentation <https://pdf-bl.github.io/pdfbl.sequential>`_.

Citation
--------

If you use pdfbl.sequential in a scientific publication, we would like you to cite this package as

        pdfbl.sequential Package, https://github.com/pdf-bl/pdfbl.sequential

Installation
------------

The preferred method is to use `Miniconda Python
<https://docs.conda.io/projects/miniconda/en/latest/miniconda-install.html>`_
and install from the "conda-forge" channel of Conda packages.

To add "conda-forge" to the conda channels, run the following in a terminal. ::

        conda config --add channels conda-forge

We want to install our packages in a suitable conda environment.
The following creates and activates a new environment named ``pdfbl.sequential_env`` ::

        conda create -n pdfbl.sequential_env pdfbl.sequential
        conda activate pdfbl.sequential_env

The output should print the latest version displayed on the badges above.

If the above does not work, you can use ``pip`` to download and install the latest release from
`Python Package Index <https://pypi.python.org>`_.
To install using ``pip`` into your ``pdfbl.sequential_env`` environment, type ::

        pip install pdfbl.sequential

If you prefer to install from sources, after installing the dependencies, obtain the source archive from
`GitHub <https://github.com/pdf-bl/pdfbl.sequential/>`_. Once installed, ``cd`` into your ``pdfbl.sequential`` directory
and run the following ::

        pip install .

This package also provides command-line utilities. To check the software has been installed correctly, type ::

        pdfbl.sequential --version

You can also type the following command to verify the installation. ::

        python -c "import pdfbl.sequential; print(pdfbl.sequential.__version__)"


To view the basic usage and available commands, type ::

        pdfbl.sequential -h

Examples
--------

To run a temperature sequential refinement, ::

        from pdfbl.sequential.sequential_cmi_runner import SequentialCMIRunner
        runner = SequentialCMIRunner()
        runner.load_inputs(
                input_data_dir="path/to/inputs",
                output_result_dir="path/to/outputs",
                structure_path="path/to/structure.cif",
                filename_order_pattern=r"(\d+)K\.gr",  # regex pattern to extract the temperature from the filename
        )
        runner.run(mode="batch")  # or mode="stream" for running sequentially as data becomes available

Getting Started
---------------

You may consult our `online documentation <https://pdf-bl.github.io/pdfbl.sequential>`_ for tutorials and API references.

Support and Contribute
----------------------

If you see a bug or want to request a feature, please `report it as an issue <https://github.com/pdf-bl/pdfbl.sequential/issues>`_ and/or `submit a fix as a PR <https://github.com/pdf-bl/pdfbl.sequential/pulls>`_.

Feel free to fork the project and contribute. To install pdfbl.sequential
in a development mode, with its sources being directly used by Python
rather than copied to a package directory, use the following in the root
directory ::

        pip install -e .

To ensure code quality and to prevent accidental commits into the default branch, please set up the use of our pre-commit
hooks.

1. Install pre-commit in your working environment by running ``conda install pre-commit``.

2. Initialize pre-commit (one time only) ``pre-commit install``.

Thereafter your code will be linted by black and isort and checked against flake8 before you can commit.
If it fails by black or isort, just rerun and it should pass (black and isort will modify the files so should
pass after they are modified). If the flake8 test fails please see the error messages and fix them manually before
trying to commit again.

Improvements and fixes are always appreciated.

Before contributing, please read our `Code of Conduct <https://github.com/pdf-bl/pdfbl.sequential/blob/main/CODE-OF-CONDUCT.rst>`_.

Contact
-------

For more information on pdfbl.sequential please visit the project `web-page <https://pdf-bl.github.io/>`_ or email Simon Billinge at sb2896@columbia.edu.

Acknowledgements
----------------

``pdfbl.sequential`` is built and maintained with `scikit-package <https://scikit-package.github.io/scikit-package/>`_.
