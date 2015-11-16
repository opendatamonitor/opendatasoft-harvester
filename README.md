opendatasoft-harvester
======================

A harvester to allow CKAN directories to keep in sync with an Opendatasoft platform store.

In order to use this tool, you need to have the CKAN harvester extension (https://github.com/okfn/ckanext-harvest)
installed and loaded for your CKAN instance.
Tested with CKAN v2.2 (http://docs.ckan.org/en/ckan-2.2/).

General
---------
The opendatasoft-harvester plugin handles the Opendatasoft Api. Also it handles the metadata transformations between the Opendatasoft and the ODM scheme.
The opendatasoft-harvester plugin uses the mongo DB as metadata repository and developed as part of the ODM project (www.opendatamonitor.eu).

Building
---------

To build and use this plugin, simply:

    git clone https://github.com/opendatamonitor/opendatasoft-harvester.git
    cd opendatasoft-harvester
    pip install -r pip-requirements.txt
    python setup.py develop

Then you will need to update your CKAN configuration to include the new harvester.  This will mean adding the
opendatasoft-harvester plugin as a plugin.  E.g.

    ckan.plugins = opendatasoft_harvest

Using
---------

After setting this up, you should be able to go to:
    http://localhost:5000/harvest

Select Register a new Catalogue
Select the Opendatasoft radiobutton

And have a new "Opendatasoft" harvest type show up when creating sources.


Licence
---------

This work implements the ckanext-harvest template (https://github.com/ckan/ckanext-harvest) and thus 
licensed under the GNU Affero General Public License (AGPL) v3.0 (http://www.fsf.org/licensing/licenses/agpl-3.0.html).
