from setuptools import setup, find_packages
import sys, os

version = '0.1'

setup(
	name='opendatasoft-harvest',
	version=version,
	description="Harvesting module to catalog Socrata datasets in CKAN",
	long_description="""\
	""",
	classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
	keywords='',
	author='Socrata',
	author_email='',
	url='http://ckan.org/wiki/Extensions',
	license='mit',
	packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
	namespace_packages=['opendatasoft', 'opendatasoft.unplugged', 'opendatasoft.unplugged.ckan'],
	include_package_data=True,
	zip_safe=False,
	install_requires=[
	        # dependencies are specified in pip-requirements.txt 
	        # instead of here
	],
	tests_require=[
		'nose',
		'mock',
	],
	test_suite = 'nose.collector',
	entry_points=\
	"""
    [ckan.plugins]
	# Add plugins here, eg
	harvest=ckanext.harvest.plugin:Harvest
	opendatasoft_harvest=opendatasoft.unplugged.ckan:OpendatasoftHarvester
	[paste.paster_command]
	harvester = ckanext.harvest.commands.harvester:Harvester
	""",
)
