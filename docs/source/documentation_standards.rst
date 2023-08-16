Code Documentation Standards
============================

docstrings
~~~~~~~~~~

Each class method should have a docstring. It should follow the `numpy <https://github.com/numpy/numpy/blob/master/doc/HOWTO_DOCUMENT.rst.txt>`_ formatting standard. 
See `this example <http://sphinxcontrib-napoleon.readthedocs.org/en/latest/example_numpy.html>`_


Rst files
~~~~~~~~~

These documentation files are reStructuredText formatted. They are processed into HTML using `Sphinx <http://www.sphinx-doc.org/en/stable/rest.html>`_.


Building the HTML Version
=========================

From ``.\doc`` run the command::

    rebuild_all.cmd
   
Check and fix the cause of any warnings or errors.

If it builds with no errors then you may want to start up an autobuild process so that you can see the html update
within a few seconds after you save any changes to the documentation source or configuration::

    autobuild.cmd


reStructuredText Header Levels
==============================

We use the following formats for the different reStructuredText header levels::

   #######
   Level 1
   #######
   
   *******
   Level 2
   *******
   
   Level 3
   ~~~~~~~
   
   Level 4
   =======
   
   Level 5
   -------
   
   Level 6
   +++++++

