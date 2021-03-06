import urllib2
import json
from ckan.lib.base import c
from ckan import model
from ckan.model import Session, Package
from ckan.logic import ValidationError, NotFound, get_action
from ckan.lib.helpers import json

from ckanext.harvestodm.model import HarvestJob, HarvestObject, HarvestGatherError, \
                                    HarvestObjectError

#from ckanclient import CkanClient

import logging
log = logging.getLogger('opendatasoft')
import datetime
from ckanext.harvestodm.harvesters.base import HarvesterBase
#from opendatasoft.unplugged.opendatasoftAdaptor import opendatasoftAdaptor
import configparser 
import pymongo

config = configparser.ConfigParser()
config.read('/var/local/ckan/default/pyenv/src/ckan/development.ini')
mongoclient=config['ckan:odm_extensions']['mongoclient']
mongoport=config['ckan:odm_extensions']['mongoport']
client=pymongo.MongoClient(str(mongoclient), int(mongoport))
db=client.odm
opendatasoft_db=db.odm
db_fetch_temp=db.fetch_temp
db_jobs=db.jobs
#document=opendatasoft_db.aggregate([{ "$group" :{"_id" : "$id", "elements" : { "$sum" : 1}}},{"$match": {"elements": {"$gt":0}}},{"$sort":{"elements":-1}}])
#j=0
#ids=[]
#while j<len(document['result']):
  #ids.append(document['result'][j]['_id'])
  #j+=1

class OpendatasoftHarvester(HarvesterBase):
    '''Harvests datasets from Opendatasoft

    This harvester is meant to take dataset references from Socrata and push them into a CKAN instance.

    This works through a two step process:
        1)  Get the list of datasets by pulling down the DCAT catalog of all datasets
        2)  Then, pull down additional metadata through the Socrata SODA API for each view

    From there, it is able to build the appropriate records for importing.
    '''

    config = None
    api_version = '2'

    def _get_dcat_endpoint(self):
        return '/api/dcat.rdf'

    def _set_config(self,config_str):
        if config_str:
            self.config = json.loads(config_str)

            if 'api_version' in self.config:
                self.api_version = self.config['api_version']

            log.debug('Using config: %r', self.config)
        else:
            self.config = {}

    def info(self):
        return {
            'name': 'opendatasoft',
            'title': 'opendatasoft',
            'description': 'Harvests remote opendatasoft datasets',
            'form_config_interface':'Text'
        }

    def validate_config(self,config):
        if not config:
            return config

        try:
            config_obj = json.loads(config)

            if 'default_tags' in config_obj:
                if not isinstance(config_obj['default_tags'],list):
                    raise ValueError('default_tags must be a list')

            if 'default_groups' in config_obj:
                if not isinstance(config_obj['default_groups'],list):
                    raise ValueError('default_groups must be a list')

                # Check if default groups exist
                context = {'model':model,'user':c.user}
                for group_name in config_obj['default_groups']:
                    try:
                        group = get_action('group_show')(context,{'id':group_name})
                    except NotFound,e:
                        raise ValueError('Default group not found')

            if 'default_extras' in config_obj:
                if not isinstance(config_obj['default_extras'],dict):
                    raise ValueError('default_extras must be a dictionary')

            if 'user' in config_obj:
                # Check if user exists
                context = {'model':model,'user':c.user}
                try:
                    user = get_action('user_show')(context,{'id':config_obj.get('user')})
                except NotFound,e:
                    raise ValueError('User not found')

            for key in ('read_only','force_all'):
                if key in config_obj:
                    if not isinstance(config_obj[key],bool):
                        raise ValueError('%s must be boolean' % key)

        except ValueError,e:
            raise e

        return config


    def gather_stage(self,harvest_job):
        log.debug('In OpendatasoftHarvester 2 gather_stage (%s)' % harvest_job.source.url)
        get_all_packages = True


        url=harvest_job.source.url.rstrip('/')+"/api/datasets/1.0/search/?rows=100000000"
        result=json.load(urllib2.urlopen(url))
        datasets=result['datasets']
        i=0
        package_ids=[]
        while i<len(datasets):
		  package_ids.append(datasets[i]['datasetid'])
		  i+=1

        #package_ids = adaptorInstance.listDatasetIds(dcatUrl)
       #print('****package ids****')
        #print(package_ids)

        
        ###load existing datasets names and ids from mongoDb
        datasets=list(opendatasoft_db.find({'catalogue_url':harvest_job.source.url}))
        datasets_ids=[]
        datasets_names=[]
        j=0
        while j<len(datasets):
		  datasets_ids.append(datasets[j]['id'])
		  j+=1

        
        
        ###check for deleted datasets that exist in mongo
        count_pkg_ids=0
        while count_pkg_ids<len(package_ids):
		  temp_pckg_id=package_ids[count_pkg_ids]
		  if temp_pckg_id in datasets_ids:
			datasets_ids.remove(temp_pckg_id)
		  count_pkg_ids+=1
        if len(datasets_ids)>0:
		#print(datasets_ids)
		j=0
		while j<len(datasets_ids):
		  i=0
		  while i<len(datasets):
			if datasets_ids[j] in datasets[i]['id']:
			  document=datasets[i]
			  document.update({"deleted_dataset":True})
			  opendatasoft_db.save(document)
			i+=1
		  j+=1

        try:
            object_ids = []
            if len(package_ids):
                for package_id in package_ids:
                    #if "http" not in package_id: 
                    # Create a new HarvestObject for this identifier
                      obj = HarvestObject(guid = package_id, job = harvest_job)
                      obj.save()
                      object_ids.append(obj.id)

                return object_ids

            else:
                self._save_gather_error('No packages received for URL: %s' % url,
                    harvest_job)
                return None
        except Exception, e:
            self._save_gather_error('%r'%e.message,harvest_job)


    def fetch_stage(self,harvest_object):
        '''
        Fetches the list of datasets from the catalog
        '''
        log.debug('In OpendatasoftHarvester fetch_stage')

        self._set_config(harvest_object.job.source.config)


        fetch_url=harvest_object.source.url.rstrip('/')+"/api/datasets/1.0/"+harvest_object.guid+"/"

        #print(fetch_url)
        
        dataset={}
        #log.debug(fetchUrl)

        try:
            response = json.load(urllib2.urlopen(fetch_url))
            dataset=response['metas']
            has_records=response['has_records']
            features=response['features']


        except Exception, e:
            log.exception('Could not load ' + fetch_url)
            self._save_gather_error('%r'%e.message,harvest_object)
        
       
        content={}
        db_jobs=db.jobs
        base_url = harvest_object.source.url
        #print(base_url)
        
        ## get language info from mongo
        language=""
        try:
          doc=db_jobs.find_one({"cat_url":str(base_url)})
          language=doc['language']
        except:
          pass


	  ## transform opendatasoft scheme to ckan scheme:
        if len(dataset.keys())>1:
		  if 'publisher' in dataset.keys():
			content.update({"author":dataset['publisher']})
		  if 'description' in dataset.keys():
			content.update({"notes":dataset['description'].replace('"','')})
		  if 'license' in dataset.keys():
			content.update({"license_id":dataset['license']})
		  if 'title' in dataset.keys():
			content.update({"title":dataset['title']})
		  if 'keyword' in dataset.keys():
			content.update({"tags":dataset['keyword']})
		  extras={}
		  if 'theme' in dataset.keys():
			extras.update({"category":dataset['theme']})
		  if 'modified' in dataset.keys():
			extras.update({"date_updated":dataset['modified']})
		  extras.update({"language":language})
		  content.update({"extras":extras})
		  content.update({"url":base_url.rstrip("/")+"/explore/dataset/"+harvest_object.guid})
		  content.update({'id':harvest_object.guid})
		  if has_records==True:
			resources=[]
			if 'geo' in features:
			  
			  resource={}
			  resource1={}
			  resource2={}
			  resource3={}
			  resource4={}
			  
			  resource.update({'url':base_url.rstrip("/")+"/explore/dataset/"+harvest_object.guid+"/download/?format=csv","format":"csv"})
			  resource1.update({'url':base_url.rstrip("/")+"/explore/dataset/"+harvest_object.guid+"/download/?format=json","format":"json"})
			  resource2.update({'url':base_url.rstrip("/")+"/explore/dataset/"+harvest_object.guid+"/download/?format=xls","format":"xls"})
			  resource3.update({'url':base_url.rstrip("/")+"/explore/dataset/"+harvest_object.guid+"/download/?format=geojson","format":"geojson"})
			  resource4.update({'url':base_url.rstrip("/")+"/explore/dataset/"+harvest_object.guid+"/download/?format=shp","format":"shp"})
			  
			  resources.append(resource)
			  resources.append(resource1)
			  resources.append(resource2)
			  resources.append(resource3)
			  resources.append(resource4)
			  content.update({"resources":resources})
			else:
			  resource={}
			  resource1={}
			  resource2={}
  
			  resource.update({'url':base_url.rstrip("/")+"/explore/dataset/"+harvest_object.guid+"/download/?format=csv","format":"csv"})
			  resource1.update({'url':base_url.rstrip("/")+"/explore/dataset/"+harvest_object.guid+"/download/?format=json","format":"json"})
			  resource2.update({'url':base_url.rstrip("/")+"/explore/dataset/"+harvest_object.guid+"/download/?format=xls","format":"xls"})
	  
			  resources.append(resource)
			  resources.append(resource1)
			  resources.append(resource2)
			  content.update({"resources":resources})


        # Save the fetched contents in the HarvestObject
        harvest_object.content = json.dumps(content)
        harvest_object.save()


        return True

    def import_stage(self,harvest_object):
        '''
        Imports each dataset from Opendatasoft, into the CKAN server
        '''
        log.debug('In OpendatasoftHarvester import_stage')
        print('In OpendatasoftHarvester import_stage')
        if not harvest_object:
            log.error('No harvest object received')
            return False

        if harvest_object.content is None:
            self._save_object_error('Empty content for object %s' % harvest_object.id,
                    harvest_object, 'Import')
            return False

        self._set_config(harvest_object.job.source.config)


        package_dict = json.loads(harvest_object.content)
     
        
        log.debug(harvest_object.job.source.config)
        try:
            #log.debug(harvest_object.content)


            package_dict.update({"catalogue_url":str(harvest_object.source.url)})
            package_dict.update({"platform":"opendatasoft"})
            package_dict.update({"name":package_dict['id'].lower().strip()})
           

            mainurl=str(harvest_object.source.url)
            #if package_dict['id'] not in ids:
            document=opendatasoft_db.find_one({"catalogue_url":harvest_object.source.url,'id':package_dict['id']})
            if document==None:
                  metadata_created=datetime.datetime.now()
                  package_dict.update({"metadata_created":str(metadata_created)})
                  opendatasoft_db.save(package_dict)
                  log.info('Metadata saved succesfully to MongoDb.')
                  fetch_document=db_fetch_temp.find_one()
		  if fetch_document==None:
			fetch_document={}
			fetch_document.update({"cat_url":mainurl})
			fetch_document.update({"new":1})
			fetch_document.update({"updated":0})
			db_fetch_temp.save(fetch_document)
		  else:
			if mainurl==fetch_document['cat_url']:
			  new_count=fetch_document['new']
			  new_count+=1
			  fetch_document.update({"new":new_count})
			  db_fetch_temp.save(fetch_document)
			else:
			  last_cat_url=fetch_document['cat_url']
			  doc=db_jobs.find_one({'cat_url':fetch_document['cat_url']})
			  if 'new' in fetch_document.keys():
				new=fetch_document['new']
				if 'new' in doc.keys():
				  last_new=doc['new']
				  doc.update({"last_new":last_new})
				doc.update({"new":new})
				db_jobs.save(doc)
			  if 'updated' in fetch_document.keys():
				updated=fetch_document['updated']
				if 'updated' in doc.keys():
				  last_updated=doc['updated']
				  doc.update({"last_updated":last_updated})
				doc.update({"updated":updated})
				db_jobs.save(doc)
			  fetch_document.update({"cat_url":mainurl})
			  fetch_document.update({"new":1})
			  fetch_document.update({"updated":0})
			  db_fetch_temp.save(fetch_document)
            else:
                  met_created=document['metadata_created']
		  if 'copied' in document.keys():
			package_dict.update({'copied':document['copied']})
                  package_dict.update({'metadata_created':met_created})
                  package_dict.update({'metadata_updated':str(datetime.datetime.now())})
                  package_dict.update({'updated_dataset':True})
                  #existing_dataset=opendatasoft_db.find_one({"id":package_dict['id'],"catalogue_url":mainurl})
                  objectid=document['_id']
                  package_dict.update({'_id':objectid})
                  opendatasoft_db.save(package_dict)
                  log.info('Metadata updated succesfully to MongoDb.')
                  fetch_document=db_fetch_temp.find_one()
		  if fetch_document==None:
			fetch_document={}
			fetch_document.update({"cat_url":mainurl})
			fetch_document.update({"updated":1})
			fetch_document.update({"new":0})
			db_fetch_temp.save(fetch_document)
		  else:
			if mainurl==fetch_document['cat_url']:
			  updated_count=fetch_document['updated']
			  updated_count+=1
			  fetch_document.update({"updated":updated_count})
			  db_fetch_temp.save(fetch_document)
			else:
			  last_cat_url=fetch_document['cat_url']
			  doc=db_jobs.find_one({'cat_url':fetch_document['cat_url']})
			  if 'new' in fetch_document.keys():
				new=fetch_document['new']
				if 'new' in doc.keys():
				  last_new=doc['new']
				  doc.update({"last_new":last_new})
				doc.update({"new":new})
				db_jobs.save(doc)
			  if 'updated' in fetch_document.keys():
				updated=fetch_document['updated']
				if 'updated' in doc.keys():
				  last_updated=doc['updated']
				  doc.update({"last_updated":last_updated})
				doc.update({"updated":updated})
				db_jobs.save(doc)
			  fetch_document.update({"cat_url":mainurl})
			  fetch_document.update({"updated":1})
			  fetch_document.update({"new":0})
			  db_fetch_temp.save(fetch_document)	



            # Set default tags if needed
            default_tags = self.config.get('default_tags',[])
            if default_tags:
                if not 'tags' in package_dict:
                    package_dict['tags'] = []
                package_dict['tags'].extend([t for t in default_tags if t not in package_dict['tags']])


            # Set default groups if needed
            default_groups = self.config.get('default_groups',[])
            if default_groups:
                if not 'groups' in package_dict:
                    package_dict['groups'] = []
                package_dict['groups'].extend([g for g in default_groups if g not in package_dict['groups']])

            log.debug(package_dict)

            result = self._create_or_update_package(package_dict,harvest_object)
            #log.debug(result)

            if result and self.config.get('read_only',False) == True:
                package = model.Package.get(package_dict['id'])

                # Clear default permissions
                model.clear_user_roles(package)

                # Setup harvest user as admin
                user_name = self.config.get('user',u'harvest')
                user = model.User.get(user_name)
                pkg_role = model.PackageRole(package=package, user=user, role=model.Role.ADMIN)

                # Other users can only read
                for user_name in (u'visitor',u'logged_in'):
                    user = model.User.get(user_name)
                    pkg_role = model.PackageRole(package=package, user=user, role=model.Role.READER)
            return True



        except ValidationError,e:
            self._save_object_error('Invalid package with GUID %s: %r' % (harvest_object.guid, e.error_dict),
                    harvest_object, 'Import')
            print('ValidationError')
        except Exception, e:
            self._save_object_error('%r'%e,harvest_object,'Import')
            print('Exception')

