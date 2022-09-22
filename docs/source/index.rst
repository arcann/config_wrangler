#################################
Config Wrangler (config_wrangler)
#################################

pydantic based configuration wrangler. Handles reading multiple **ini** or **toml** files with inheritance rules and variable expansions.

This tool grew out of the limitations discovered using ConfigParser with a multiple large ETL loads using the
`bi_etl <https://bietl.dev/bi_etl/>`_ framework.

    - Validate the configuration files at startup and not hours into the program run.
        e.g. ConfigParser.getint() would fail deep into a run when reading a non-integer value
    - Needed a clean way to support configuration items that might be either environment specific or shared across environments (checked into git).
    - Needed to have configuration items that are shared across multiple programs while also having some that are specific to each program. Also wanted to avoid a single huge monolith config file -- that due to the validation had to all be valid in order for any single program that used part of it to startup successfully.

This project on PyPI: `config-wrangler <https://pypi.org/project/config-wrangler>`_

*************************
Installation
*************************

Install using your package manager of choice:
  - `poetry add config-wrangler`
  - `pip install -U config-wrangler`
  - `conda install config-wrangler -c conda-forge`.


************************
Parts of config_wrangler
************************

.. toctree::
    :maxdepth: 1

    config_templates_modules
    simple_example
    documentation_standards

************
Modules APIs
************
.. toctree::
   :maxdepth: 3

   config_wrangler


******************
Indices and tables
******************

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

