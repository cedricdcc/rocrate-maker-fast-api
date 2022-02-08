from fastapi import FastAPI, Path, Query, HTTPException, status, APIRouter
from fastapi.openapi.utils import get_openapi
from typing import List, Optional, Set
from pydantic import BaseModel, Field
import os, json, requests, asyncio, sys, aiohttp, shutil, git, uuid, subprocess, stat
from importlib import import_module
from datetime import datetime
from aiohttp import ClientSession
from rocrate.rocrate import ROCrate
from pathlib import Path as pads
from collections import MutableMapping
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import (
    get_redoc_html,
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)
import app.shacl_helper as shclh

router = APIRouter(
    prefix="/annotation",
    tags=["Annotation"],
    responses={404: {"description": "Not found"}},
)

## import the config file for the specific route of the api ##
from dotenv import load_dotenv
load_dotenv()
BASE_URL_SERVER = os.getenv('BASE_URL_SERVER')

### define class profiles for the api ###

class ProfileModel(BaseModel):
    logo: Optional[str] = Field(None, example = 'https://www.researchobject.org/ro-crate/assets/img/ro-crate-w-text.png', description = "Logo to be displayed in RO crate UI")
    description: Optional[str] = Field(None, description = "description of the RO-profile")
    url_ro_profile: str = Field(None, description = "github url where the rocrate profile is located")

class SpaceModel(BaseModel):
    storage_path: str = Field(None, description = "Valid path on local storage where ROcrate data will be stored")
    RO_profile: str = Field(None, description = "Ro-Profile name that will be used for the space")
    remote_url: Optional[str] = Field(None, description = "git repo url to get project from")

class FileModel(BaseModel):
    name     : str = Field(None, description = "Name of the file that will be added, can be filepath")
    content  : str = Field(None, description = "Filepath that needs to be added to the space, can also be a directory or url")
    
class AnnotationModel(BaseModel):
    URI_predicate_name : str = Field(None, description = "Name of the URI that will be added, must be part of the RO-crate profile provided metadata predicates.\
                                                for more info about the allowed predicates, use TODO: insert api call for predicates here.")
    value    : str = Field(None, description = "Value linked to the URI predicate name chosen")

class AnnotationsModel(BaseModel):
    Annotations: List[AnnotationModel] = Field(None, description = "List of annotations to add to resource. \
                                              for more info about the allowed annotation predicates, use TODO: insert api call for predicates here.")

class ContentModel(BaseModel):
    content: List[FileModel] = Field(None, description = "List of files that need to be added, this list can also contain directories")

class DeleteContentModel(BaseModel):
    content: List[str] = Field(None, description = "List of files to delete , if full path given it will delete one file , of only file name given it will delete all entities in the system with file name.")

### define helper functions for the api ###

#TODO: function that reads into the roprofile rocrate metadata and finds the conforms to part ;
#  1: gets the shacl or other constraint files.
#  2: reciprocly go through all rocrate conform to untill all contraints are gathered. 
#  3: combines all the contraints into 1 contraint file and return this in a folder that is a sibling of the project folder.

#TODO: function that searches for the typechanger for mimetypes when adding new files to the rocrate , be it either from url or from local system

#TODO: figure out how to get the mimetype of url resources added (maybe through name?)

#TODO: function that reads the shacl contraint file and gets the right properties for an accordingly chosen schema target class (@type in rocrate metadata.json)

def check_space_name(spacename):
    with open(os.path.join(os.getcwd(),"app","webtop-work-space","spaces.json"), "r+")as file:
        data = json.load(file)
    for space, info in data.items():
        if spacename == space:
            return True
    return False

def on_rm_error(func, path, exc_info):
    #from: https://stackoverflow.com/questions/4829043/how-to-remove-read-only-attrib-directory-with-python-in-windows
    os.chmod(path, stat.S_IWRITE)
    os.unlink(path)

async def check_path_availability(tocheckpath,space_id):
    if os.path.isdir(os.path.join(tocheckpath)) == False:
        raise HTTPException(status_code=400, detail="Given storage path does not exist on local storage")
    #check if given path is already used by another project
    toposturl = 'http://localhost:6656/apiv1/spaces' #TODO : figure out how to not hardcode this <---
    async with ClientSession() as session:
        response = await session.request(method='GET', url=toposturl)
        text = await response.content.read()
        all_spaces = json.loads(text.decode('utf8').replace("'", '"'))
        for space,info_space in all_spaces.items():
            print(info_space["storage_path"], file=sys.stderr)
            print(str("/".join((tocheckpath,str(space_id)))), file=sys.stderr)
            if info_space['storage_path'] == str("/".join((tocheckpath,str(space_id)))) or info_space['storage_path'] == str(tocheckpath):
                raise HTTPException(status_code=400, detail="Given storage path is already in use by another project")
    if len(os.listdir(os.path.join(tocheckpath)) ) != 0:
        try:
            os.mkdir(os.path.join(tocheckpath,str(space_id)))
            tocheckpath = os.path.join(tocheckpath,str(space_id))
            returnmessage = "Space created in folder: " + str(os.path.join(tocheckpath))
            return [returnmessage,tocheckpath]
        except:
            tocheckpath = os.path.join(tocheckpath,str(space_id))
            returnmessage = "Space created in existing folder: " + str(os.path.join(tocheckpath))
            return [returnmessage,tocheckpath]

### api paths ###

### space resource annotation ###

@router.get('/', status_code=200)
def get_all_resources_annotation(*,space_id: str = Path(None,description="space_id name")):
    with open(os.path.join(os.getcwd(),"app","webtop-work-space","spaces.json"), "r+") as file:
        data = json.load(file)
        try:
            space_folder = data[space_id]['storage_path']
        except Exception as e:
            raise HTTPException(status_code=404, detail="Space not found")
    #read in ROCrate metadata file
    with open(os.path.join(space_folder,'repo','ro-crate-metadata.json'), "r+") as projectfile:
        #print(projectfile)
        data = json.load(projectfile)
        all_files = []
        #get all files from the projectfile
        for dictionaries in data["@graph"]:
            for item, value in dictionaries.items():
                if item == "@id":
                    all_files.append(value)
        print(all_files)
        #foreach file get all the attributes
        files_attributes = {}
        for file in all_files:
            if file != "ro-crate-metadata.json" and file != './':
                if "." in file:
                    files_attributes[file]= {}
                    clicktrough_url = BASE_URL_SERVER + 'apiv1/' + 'spaces/' + space_id + '/annotation/file/' + file
                    files_attributes[file]['url_file_metadata'] = clicktrough_url
                    for dictionaries in data["@graph"]:
                        for item, value in dictionaries.items():
                            if item == "@id" and value==file:
                                for item_save, value_save in dictionaries.items():
                                    files_attributes[file][item_save] = value_save
    return {"data":files_attributes}


@router.post('/file/{file_id}', status_code=200)
def make_resource_annotation_single_file(*,space_id: str = Path(None,description="space_id name"), file_id: str = Path(None,description="id of the file that will be searched in the ro-crate-metadata.json file"), item: AnnotationsModel):
    ## get the current metadata.json ##
    with open(os.path.join(os.getcwd(),"app","webtop-work-space","spaces.json"), "r+") as file:
        data = json.load(file)
        try:
            space_folder = data[space_id]['storage_path']
        except Exception as e:
            raise HTTPException(status_code=404, detail="Space not found")
    #read in ROCrate metadata file
    with open(os.path.join(space_folder,'repo','ro-crate-metadata.json'), "r+") as projectfile:
        #print(projectfile)
        data = json.load(projectfile)
    ## get constraint values from shacl file for file ##
    path_shacl = os.path.join(space_folder,"workspace","all_constraints.ttl")
    print(path_shacl, file=sys.stderr)
    test = shclh.ShapesInfoGraph(path_shacl)
    shacldata = test.full_shacl_graph_dict()
    #convert the chacl file to have all the properties per node id
    node_properties_dicts = []
    for node_to_check in shacldata:
        toaddnode = {}
        if node_to_check["target"] is not None:
            target = node_to_check["target"].split("/")[-1]
            toaddnode[target] = []
            for propname , semantic_properties in node_to_check["properties"].items():
                #add reciproce checking for nodes in nodes here 
                
                toaddnode[target].append({propname.split('/')[-1]: semantic_properties})
            node_properties_dicts.append(toaddnode)
    
    print(node_properties_dicts, file=sys.stderr)
    
    all_files = []
    all_predicates = []
    #get all files from the projectfile
    for dictionaries in data["@graph"]:
        for iteme, value in dictionaries.items():
            if iteme == "@id" and value == file_id:
                for item_save, value_save in dictionaries.items():
                    all_predicates.append(item_save)
                    all_files.append({'predicate':item_save,'value':value_save})
    
    if len(all_predicates) == 0:
        raise HTTPException(status_code=404, detail="Resource not found.")
    
    ## for each annotation given ##
    warnings = []
    print(item, file=sys.stderr)
    for annotationfile in item.Annotations:
        uri_name  = annotationfile.URI_predicate_name
        value_uri = annotationfile.value
        
        ## check if annotation is in the shacl file ##
        for predicates in all_files:
            find_now = 0
            for itemee, value in predicates.items():
                if itemee == 'predicate' and value == "@type":
                    find_now = 1
                if itemee == "value" and find_now == 1:
                    to_search_type = value
        print(to_search_type, file=sys.stderr)
        for node in node_properties_dicts:
            for nodekey, nodevalue in node.items():
                if nodekey == to_search_type:
                    all_props = []
                    for prop in nodevalue:
                        for propkey, propvalue in prop.items():
                            propmin = 0
                            for propattribute, propattributevalue in propvalue.items():
                                print(propattribute, file=sys.stderr)
                                print(propattributevalue, file=sys.stderr)
                                if propmin == 0:
                                    if propattribute == "min" and propattributevalue is not None:
                                        propmin = 1
                                
                                if propattribute == "type" and propattributevalue is not None:
                                    proptype = propattributevalue
                                
                                if propattribute == "type" and propattributevalue is None:
                                    proptype = 'String'
                                
                                if propattribute == "values" and propattributevalue is not None:
                                    valueprop = propattributevalue
                                        
                            all_props.append({propkey:{'min':propmin,'value':valueprop,'typeprop':proptype}})

                        print(all_props, file=sys.stderr)
        chacl_URI_list = []
        for diff_kind_annotations in all_props:
            for key_annotation , metadata_annotation in diff_kind_annotations.items():
                chacl_URI_list.append(key_annotation)
        print("chacl_list_printed: ", file=sys.stderr)
        print(chacl_URI_list, file=sys.stderr)
        for ids in data['@graph']:
                if ids['@id'] == file_id:
                    ids[uri_name]= value_uri
        if uri_name not in chacl_URI_list:
            warnings.append("non shacl defined constraint metadata has been added: "+ uri_name)
            
        ## implement annotation in the data is found , send warning message is annotation title not found in constraints ##
    ## write back to metadata file and return metadata.json file 
    tocheck_folder = os.path.join(space_folder,"repo")
    with open(os.path.join(tocheck_folder, 'ro-crate-metadata.json'), 'w') as json_file:
        json.dump(data, json_file)
        
    return {"Data":data, "Warnings":warnings}

@router.delete('/file/{file_id}/{predicate}', status_code=200)
def delete_resource_annotation(*,space_id: str = Path(None,description="space_id name"), file_id: str = Path(None,description="id of the file that will be searched in the ro-crate-metadata.json file"), predicate: str = Path(None,description="To delete predicate from the file annotations")):
    with open(os.path.join(os.getcwd(),"app","webtop-work-space","spaces.json"), "r+") as file:
        data = json.load(file)
        try:
            space_folder = data[space_id]['storage_path']
        except Exception as e:
            raise HTTPException(status_code=404, detail="Space not found")
    
    tocheck_folder = os.path.join(space_folder,"repo")
    todelete = False
    #load in metadata files
    with open(os.path.join(tocheck_folder, 'ro-crate-metadata.json')) as json_file:
        data = json.load(json_file)

    #find id of file and delete predicate of existing 
    for ids in data['@graph']:
        if ids['@id'] == file_id:
            todelete = True
            try:
                ids.pop(predicate)
            except:
                raise HTTPException(status_code=404, detail="predicate not found")
            
    if todelete != True:
        raise HTTPException(status_code=404, detail="file_id not found")
                        
    #write back data to meta json file
    with open(os.path.join(tocheck_folder, 'ro-crate-metadata.json'), 'w') as json_file:
        json.dump(data, json_file)
        
    return {"Data":data}

@router.get('/file/{file_id}', status_code=200)
def get_resource_annotation(*,space_id: str = Path(None,description="space_id name"), file_id: str = Path(None,description="id of the file that will be searched in the ro-crate-metadata.json file")):
    with open(os.path.join(os.getcwd(),"app","webtop-work-space","spaces.json"), "r+") as file:
        data = json.load(file)
        try:
            space_folder = data[space_id]['storage_path']
        except Exception as e:
            raise HTTPException(status_code=404, detail="Space not found")
    #read in ROCrate metadata file
    with open(os.path.join(space_folder,'repo','ro-crate-metadata.json'), "r+") as projectfile:
        #print(projectfile)
        data = json.load(projectfile)
        all_files = []
        
        #implement the shacl constraint check here
        #read in shacl file
        path_shacl = os.path.join(space_folder,"workspace","all_constraints.ttl")
        f_constraints = open(path_shacl, "r")
        f_constraints_text = f_constraints.read()
        print(path_shacl, file=sys.stderr)
        test = shclh.ShapesInfoGraph(path_shacl)
        shacldata = test.full_shacl_graph_dict()
        #convert the chacl file to have all the properties per node id
        node_properties_dicts = []
        for node_to_check in shacldata:
            toaddnode = {}
            if node_to_check["target"] is not None:
                target = node_to_check["target"].split("/")[-1]
                toaddnode[target] = []
                for propname , semantic_properties in node_to_check["properties"].items():
                    #add reciproce checking for nodes in nodes here
                    toaddnode[target].append({propname.split('/')[-1]: semantic_properties})
                node_properties_dicts.append(toaddnode)
        
        print(node_properties_dicts, file=sys.stderr)
                 
        all_predicates = []
        #get all files from the projectfile
        for dictionaries in data["@graph"]:
            for item, value in dictionaries.items():
                if item == "@id" and value == file_id:
                    for item_save, value_save in dictionaries.items():
                        all_predicates.append(item_save)
                        all_files.append({'predicate':item_save,'value':value_save})
        
        if len(all_predicates) == 0:
            raise HTTPException(status_code=404, detail="Resource not found.")
        
        #get all predicates and if they are required
        for items in all_files:
            if items["predicate"] == "@type":
                for node in node_properties_dicts:
                    for nodekey, nodevalue in node.items():
                        if nodekey == items["value"]:
                            all_props = []
                            all_props_shacl = []
                            for prop in nodevalue:
                                for propkey, propvalue in prop.items():
                                    propmin = 0
                                    for propattribute, propattributevalue in propvalue.items():
                                        print(propattribute, file=sys.stderr)
                                        print(propattributevalue, file=sys.stderr)
                                        if propmin == 0:
                                            if propattribute == "min" and propattributevalue is not None:
                                                propmin = 1
                                        if propattribute == "type" and propattributevalue is not None:
                                            proptype = propattributevalue
                                        if propattribute == "type" and propattributevalue is None:
                                            proptype = 'String'
                                        if propattribute == "values" and propattributevalue is not None:
                                            valueprop = propattributevalue                                             
                                    all_props.append({propkey:{'min':propmin,'value':valueprop,'typeprop':proptype}})
                                    all_props_shacl.append({'label':propkey,'min':propmin,'value':valueprop,'typeprop':proptype})
                                print(all_props, file=sys.stderr)
        try:                              
            present = 0
            missing = 0
            cond_present = 0
            cond_missing = 0
            for prop in all_props:
                for propkey, propvalue in  prop.items():
                    if propvalue['min'] == 1 and propkey not in all_predicates:
                        missing+=1
                    if propvalue['min'] != 1 and propkey not in all_predicates:
                        cond_missing+=1
                    if propvalue['min'] != 1 and propkey in all_predicates:
                        cond_present+=1
                    if propvalue['min'] == 1 and propkey in all_predicates:
                        present+=1
            
            green_percent = ((present / len(all_props)) * 100) + ((cond_present / len(all_props)) * 100)
            red_percent   = (missing / len(all_props)) * 100
            orange_percent = (cond_missing / len(all_props)) * 100
            summary_file = {'green': green_percent, 'orange': orange_percent, 'red': red_percent} 
        except Exception as e:
            print(e, file=sys.stderr)
            summary_file = {'green': 0, 'orange': 0, 'red': 0} 
        return {'data':all_files, 'summary': summary_file, 'shacl_requirements': all_props_shacl, 'shacl_original': f_constraints_text}
    
       
#TODO : Add content modal for the annotation of the resources

@router.get('/terms', status_code=200)
def get_terms_shacl(*, space_id: str = Path(None,description="space_id name")):
    #TODO from json select which shacl file should be taken
    with open(os.path.join(os.getcwd(),"app","webtop-work-space","spaces.json"), "r+") as file:
        data = json.load(file)
        try:
            space_folder = data[space_id]['storage_path']
        except Exception as e:
            raise HTTPException(status_code=404, detail="Space not found")
    #read in shacl file 
    path_shacl = os.path.join(space_folder,"workspace","all_constraints.ttl")
    print(path_shacl, file=sys.stderr)
    test = shclh.ShapesInfoGraph(path_shacl)
    shacldata = test.full_shacl_graph_dict()
    return shacldata

@router.patch('/{path_folder:path}', status_code=200)
def make_resource_annotations(*,space_id: str = Path(None,description="space_id name"), path_folder: str = Path(None,description="folder-path to the file relative to where the space is stored"), item: AnnotationsModel):
    #get path of metadatafile
    with open(os.path.join(os.getcwd(),"app","webtop-work-space","spaces.json"), "r+") as file:
        data = json.load(file)
        try:
            space_folder = data[space_id]['storage_path']
        except Exception as e:
            raise HTTPException(status_code=404, detail="Space not found")
    #get all the files under the path folder 
    space_foldere = os.path.join(space_folder,"repo", path_folder)
    tocheck_folder = os.path.join(space_folder,"repo")
    print(tocheck_folder , file=sys.stderr)
    all_files = []
    for root, dirs, files in os.walk(space_foldere, topdown=False):   
        for name in files:
            print(name , file=sys.stderr)
            all_files.append(name)
    
    #load in metadata files
    with open(os.path.join(tocheck_folder, 'ro-crate-metadata.json')) as json_file:
        data = json.load(json_file)
    
    #annotate all the files according to annotations given 
    for to_annotate in all_files:
        if to_annotate != "ro-crate-metadata.json":
            all_annotations = item.Annotations
            for annotation in all_annotations:
                print("current annotation: "+ annotation.URI_predicate_name, file=sys.stderr)
                for ids in data['@graph']:
                    if ids['@id'] == to_annotate:
                        ids[annotation.URI_predicate_name]= annotation.value

    #write back data to meta json file
    with open(os.path.join(tocheck_folder, 'ro-crate-metadata.json'), 'w') as json_file:
        json.dump(data, json_file)
        
    return {"Data":data}

@router.patch('/', status_code=200)
def make_annotations_for_all_resources(*,space_id: str = Path(None,description="space_id name"), item: AnnotationsModel):
    #get path of metadatafile
    with open(os.path.join(os.getcwd(),"app","webtop-work-space","spaces.json"), "r+") as file:
        data = json.load(file)
        try:
            space_folder = data[space_id]['storage_path']
        except Exception as e:
            raise HTTPException(status_code=404, detail="Space not found")
    space_folder = os.path.join(space_folder,"repo")
    #get all the files under the path folder 
    all_files = []
    for root, dirs, files in os.walk(space_folder, topdown=False):   
        for name in files:
            all_files.append(name)
    
    #load in metadata files
    with open(os.path.join(space_folder, 'ro-crate-metadata.json')) as json_file:
        data = json.load(json_file)
    
    #annotate all the files according to annotations given 
    for to_annotate in all_files:
        all_annotations = str(item.Annotations)
        for annotation in all_annotations:
            print(annotation, file=sys.stderr)
            for ids in data['@graph']:
                if ids['@id'] == to_annotate:
                    ids[annotation.URI_predicate_name]= annotation.value

    #write back data to meta json file
    with open(os.path.join(space_folder, 'ro-crate-metadata.json'), 'w') as json_file:
        json.dump(data, json_file)
        
    return {"Data":data}

@router.delete('/{path_folder:path}', status_code=200)
def delete_resource_annotations(*,space_id: str = Path(None,description="space_id name"), path_folder: str = Path(None,description="folder-path to the file"), item: AnnotationsModel):
    #get path of metadatafile
    with open(os.path.join(os.getcwd(),"app","webtop-work-space","spaces.json"), "r+") as file:
        data = json.load(file)
        try:
            space_folder = data[space_id]['storage_path']
        except Exception as e:
            raise HTTPException(status_code=404, detail="Space not found")
    #get all the files under the path folder 
    space_foldere = os.path.join(space_folder,"repo", path_folder)
    tocheck_folder = os.path.join(space_folder,"repo")
    print(tocheck_folder , file=sys.stderr)
    all_files = []
    for root, dirs, files in os.walk(space_foldere, topdown=False):   
        for name in files:
            print(name , file=sys.stderr)
            all_files.append(name)
    
    #load in metadata files
    with open(os.path.join(tocheck_folder, 'ro-crate-metadata.json')) as json_file:
        data = json.load(json_file)
    
    #annotate all the files according to annotations given 
    for to_annotate in all_files:
        if to_annotate != "ro-crate-metadata.json":
            all_annotations = item.Annotations
            for annotation in all_annotations:
                print("current annotation: "+ annotation.URI_predicate_name, file=sys.stderr)
                for ids in data['@graph']:
                    if ids['@id'] == to_annotate:
                        try:
                            ids.pop(annotation.URI_predicate_name)
                        except:
                            pass

    #write back data to meta json file
    with open(os.path.join(tocheck_folder, 'ro-crate-metadata.json'), 'w') as json_file:
        json.dump(data, json_file)
        
    return {"Data":data}

@router.delete('/', status_code=200)
def delete_annotations_for_all_resources(*,space_id: str = Path(None,description="space_id name"), item: AnnotationsModel):
    #get path of metadatafile
    with open(os.path.join(os.getcwd(),"app","webtop-work-space","spaces.json"), "r+") as file:
        data = json.load(file)
        try:
            space_folder = data[space_id]['storage_path']
        except Exception as e:
            raise HTTPException(status_code=404, detail="Space not found")
    space_folder = os.path.join(space_folder,"repo")
    #get all the files under the path folder 
    all_files = []
    for root, dirs, files in os.walk(space_folder, topdown=False):   
        for name in files:
            all_files.append(name)
    
    #load in metadata files
    with open(os.path.join(space_folder, 'ro-crate-metadata.json')) as json_file:
        data = json.load(json_file)
    
    #annotate all the files according to annotations given 
    for to_annotate in all_files:
        all_annotations = str(item.Annotations)
        for annotation in all_annotations:
            print(annotation, file=sys.stderr)
            for ids in data['@graph']:
                if ids['@id'] == to_annotate:
                    ids.pop(annotation.URI_predicate_name)

    #write back data to meta json file
    with open(os.path.join(space_folder, 'ro-crate-metadata.json'), 'w') as json_file:
        json.dump(data, json_file)
        
    return {"Data":data}