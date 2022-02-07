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
import app.ro_crate_reader_functions as ro_read

#all diff subroutes
from .content import router as content_router
from .git import router as git_router
from .annotation import router as annotation_router

router = APIRouter(
    prefix="",
    responses={404: {"description": "Not found"}},
)
router.include_router(content_router, prefix="/{space_id}")
router.include_router(git_router, prefix="/{space_id}")
router.include_router(annotation_router, prefix="/{space_id}")

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

def complete_metadata_crate(source_path_crate):
    
    ## get all the file_ids with their metadata ##
    #open up the metadata.json file
    with open(os.path.join(source_path_crate, 'ro-crate-metadata.json')) as json_file:
        datao = json.load(json_file)
        
    #check if the ids from relation are present in the json file
    all_meta_ids_data = []
    for id in datao['@graph']:
        toappend_id = {}
        toappand_data_values = []
        for key_id, value_id in id.items():
            if key_id != "@id":
                toappand_data_values.append({key_id:value_id})
        toappend_id[id['@id']] = toappand_data_values
        all_meta_ids_data.append(toappend_id)
    
    print(all_meta_ids_data, file=sys.stderr)
    
    ## start from fresh file with metadata template  ##
    with open(os.path.join(os.getcwd(),'app', 'ro-crate-metadata.json')) as json_file:
        data = json.load(json_file)
        
    print( data, file=sys.stderr)
    
    
    ## add data to the fresh file ##
      
    relation = []
    for root, dirs, files in os.walk(source_path_crate, topdown=False):   
        for name in files:
            if root.split(source_path_crate)[-1] == "":
                parent_folder = ""
                relative_path = "./"
            else:
                relative_path = root.split(source_path_crate)[-1]
                parent_folder = relative_path.split(os.path.sep)[-1]
            relation.append({'parent_folder':parent_folder,"relative_path":relative_path,"name":name})
    all_ids = []
    for x in relation:
        #print(x)
        all_ids.append(x["name"])
    
    #check if the ids from relation are present in the json file
    all_meta_ids = []
    for id in data['@graph']:
        all_meta_ids.append(id['@id'])
        #print(id['@id'])
    for i in all_ids: 
        if i not in all_meta_ids:
            #print("not present: "+ i)
            #check if parent is present in the file
            
            def add_folder_path(path_folder):
                toaddppaths = path_folder.split("\\")
                previous = "./"
                for toadd in toaddppaths:         
                    if str(toadd+"/") not in all_meta_ids:
                        if toadd != "":
                            data['@graph'].append({'@id':toadd+"/", '@type':"Dataset", 'hasPart':[]})
                            # add ro right haspart
                            for ids in data['@graph']:
                                if ids['@id'] == previous:
                                    try:
                                        ids['hasPart'].append({'@id':toadd+"/"})
                                    except:
                                        ids['hasPart'] = []
                                        ids['hasPart'].append({'@id':toadd+"/"})
                            all_meta_ids.append(str(toadd+"/"))
                    if toadd == "":
                        previous = './'
                    else:
                        previous = toadd+"/"
                        
                            
            for checkparent in relation:
                if checkparent['name'] == i:
                    if str(checkparent['parent_folder']+"/") not in all_meta_ids:
                        if checkparent['parent_folder'] != "":
                            #make the parent_folder in ids
                            data['@graph'].append({'@id':checkparent['parent_folder']+"/", '@type':"Dataset", 'hasPart':[]})
                            #check if folder has no parent
                            if len(checkparent['relative_path'].split("\\")) == 2:
                                print(checkparent['relative_path'].split("\\"))
                                for ids in data['@graph']:
                                    if ids['@id'] == './':
                                        if {'@id':checkparent['relative_path'].split("\\")[-1]+"/"} not in ids['hasPart']:
                                            ids['hasPart'].append({'@id':checkparent['relative_path'].split("\\")[-1]+"/"})
                            
                            add_folder_path(checkparent['relative_path'])
                    #add the non present id to the folder haspart
                    for ids in data['@graph']:
                        if checkparent['parent_folder'] == "":
                            if ids['@id'] == "."+checkparent['parent_folder']+"/":
                                ids['hasPart'].append({'@id':i})
                        else:
                            if ids['@id'] == checkparent['parent_folder']+"/":
                                ids['hasPart'].append({'@id':i})
            #add the id to the @graph
            data['@graph'].append({'@id':i, '@type':"File"})
            #add id to ./ folder if necessary
    
    #remove duplicates
    seen_ids = []
    for ids in data['@graph']:
        if ids['@id'] in seen_ids:
            data['@graph'].remove(ids)
        else:
            seen_ids.append(ids['@id'])
    
    ## add file_ids metadata correspondingly ##
    for ids in data['@graph']:
        for tocheck_id in all_meta_ids_data:
            if ids['@id'] in str(tocheck_id.keys()):
                for dict_single_metadata in tocheck_id[ids['@id']]:
                    for key_dict_single_meta, value_dcit_sinle_meta in dict_single_metadata.items():
                        if key_dict_single_meta not in ids.keys():
                            print(key_dict_single_meta, file=sys.stderr)
                            ids[key_dict_single_meta] = value_dcit_sinle_meta
                            
    #write the rocrate file back 
    with open(os.path.join(source_path_crate, 'ro-crate-metadata.json'), 'w') as json_file:
        json.dump(data, json_file)

    return data

def check_space_name(spacename):
    with open(os.path.join(os.getcwd(),"app","projects.json"), "r+")as file:
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
        try:
            for space,info_space in all_spaces.items():
                print(info_space["storage_path"], file=sys.stderr)
                print(str("/".join((tocheckpath,str(space_id)))), file=sys.stderr)
                if info_space['storage_path'] == str("/".join((tocheckpath,str(space_id)))) or info_space['storage_path'] == str(tocheckpath):
                    raise HTTPException(status_code=400, detail="Given storage path is already in use by another project")
        except:
            pass
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

@router.get('/', tags=["Spaces"])
def get_all_spaces():
    with open(os.path.join(os.getcwd(),"app","projects.json"), "r+")as file:
        data = json.load(file)
        toreturn = []
        for i,y in data.items():
            clicktrough_url = BASE_URL_SERVER + 'apiv1/' + 'spaces/' + i 
            #example_url: https://example.org/dmbon/ns/entity_types#Space
            toreturn.append({'name':i,
                             'storage_path':y['storage_path'],
                             'RO_profile':y['RO_profile'],
                             '@type':'https://example.org/dmbon/ns/entity_types#Space',
                             'url_space':clicktrough_url})
            
        return toreturn

@router.get('/{space_id}/', tags=["Spaces"])
def get_space_info(*,space_id: str = Path(None,description="space_id name")):
    if check_space_name(space_id):
        with open(os.path.join(os.getcwd(),"app","projects.json"), "r+") as file:
            data = json.load(file)
            try:
                for i,y in data.items():
                    if i == space_id:
                        clicktrough_url = BASE_URL_SERVER + 'apiv1/' + 'spaces/' + i 
                        #example_url: https://example.org/dmbon/ns/entity_types#Space
                        toreturn= { 'name':i,
                                    'storage_path':y['storage_path'],
                                    'RO_profile':y['RO_profile'],
                                    '@type':'https://example.org/dmbon/ns/entity_types#Space',
                                    'url_content':clicktrough_url+"/content",
                                    'url_metadata':clicktrough_url+"/annotation",
                                    'url_constraints':clicktrough_url+"/annotation/terms"}
                
                return toreturn
            except Exception as e:
                raise HTTPException(status_code=500, detail=e)
    else:
        raise HTTPException(status_code=404, detail="Space not found")

@router.delete('/{space_id}/', status_code=202, tags=["Spaces"])
def delete_space(*,space_id: str = Path(None,description="space_id name")):
    with open(os.path.join(os.getcwd(),"app","projects.json")) as data_file:
            data = json.load(data_file)
            try:
                #delete the folder where the project was stored
                shutil.rmtree(data[space_id]["storage_path"])
            except:
                try:
                    for i in os.listdir(data[space_id]["storage_path"]):
                        if i.endswith('git'):
                            tmp = os.path.join(data[space_id]["storage_path"], i)
                            # We want to unhide the .git folder before unlinking it.
                            while True:
                                subprocess.call(['attrib', '-H', tmp])
                                break
                            shutil.rmtree(tmp, onerror=on_rm_error)
                    shutil.rmtree(data[space_id]["storage_path"])
                except Exception as e:
                    raise HTTPException(status_code=500, detail="Space delete failed {}".format(e)) 
            del data[space_id]
            
    with open(os.path.join(os.getcwd(),"app","projects.json"), 'w') as data_file:
        data = json.dump(data, data_file)    
        return {'message':'successfully deleted space'}

@router.post('/', status_code=201, tags=["Spaces"])
async def add_space(*,item: SpaceModel):
    tocheckpath = str(item.storage_path)
    returnmessage = "Space created in folder: " + str(os.path.join(tocheckpath))
    space_id = uuid.uuid4().hex
    with open(os.path.join(os.getcwd(),"app","projects.json"), "r+")as file:
        data = json.load(file)
        if space_id in data.keys():
            raise HTTPException(status_code=400, detail="Space already exists")
        check_aval = await check_path_availability(tocheckpath,space_id)
        returnmessage = check_aval[0]
        tocheckpath = check_aval[1]
        toposturl = 'http://localhost:6656/apiv1/profiles/'+str(item.RO_profile)  #TODO : figure out how to not hardcode this <---
        async with ClientSession() as session:
            response = await session.request(method='GET', url=toposturl)
            print(response.status, file=sys.stderr)
            if response.status != 200:
                raise HTTPException(status_code=400, detail="Given RO-profile does not exist")
            if response.status == 200:
                os.mkdir(os.sep.join((tocheckpath,'constraints')))
                urlprofile = (await response.json())['url_ro_profile']
                print('json file profile:  ',urlprofile, file=sys.stderr)
                secondtest = ro_read.rocrate_helper(urlprofile)
                secondtest.get_all_metadata_files()
                secondtest.get_ttl_files()
                with open(os.path.join(tocheckpath,'constraints','all_constraints.ttl'), 'w') as file:  # Use file to refer to the file object
                    file.write(secondtest.ttlinfo)
                data[space_id]= {'storage_path':tocheckpath,'RO_profile':item.RO_profile}
    
    if item.remote_url != None and item.remote_url != "string" and  item.remote_url != "":
        try:
            git.Repo.clone_from(item.remote_url, os.path.join(tocheckpath))
            repo = git.Repo(os.path.join(tocheckpath))
            #check if rocratemetadata.json is present in git project
            print("before file found", file=sys.stderr)
            if os.path.isfile(os.path.join(tocheckpath, 'ro-crate-metadata.json')) == False and os.path.isfile(os.path.join(tocheckpath, 'repo', 'ro-crate-metadata.json')) == False:
                currentwd = os.getcwd()
                os.mkdir(os.sep.join((tocheckpath,'repo')))
                os.chdir(os.sep.join((tocheckpath,'repo')))
                crate = ROCrate() 
                crate.write_crate(os.sep.join((tocheckpath,'repo')))
                os.chdir(currentwd)
                repo.git.add(all=True)
                repo.index.commit("initial commit")
                repo.create_head('master')
                    
            with open(os.path.join(os.getcwd(),"app","projects.json"), "w") as file: 
                    json.dump(data, file)
            return {'Message':returnmessage, 'space_id': space_id}
        
        except:
            try:
                #clone the git repo again but in the project folder that is made
                check_aval = await check_path_availability(str(item.storage_path),space_id)
                tocheckpath = check_aval[1]
                git.Repo.clone_from(item.remote_url, os.path.join(tocheckpath,"repo"))
                #make the ro-crate-metadata.json file 
                shutil.copyfile(os.path.join(os.getcwd(),"app","ro-crate-metadata.json"),os.sep.join((tocheckpath,'repo',"ro-crate-metadata.json")))
                with open(os.path.join(os.getcwd(),"app","projects.json"), "w") as file: 
                    json.dump(data, file)
                return {'Message':returnmessage, 'space_id': space_id}
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))
    else:
        #try and init a git repo and a rocrate
        currentwd = os.getcwd()
        os.mkdir(os.sep.join((tocheckpath,'repo')))
        os.chdir(os.sep.join((tocheckpath,'repo')))
        repo = git.Repo.init(os.path.join(tocheckpath, 'repo'))
        #change current wd to init the rocrate
        crate = ROCrate() 
        crate.write_crate(os.sep.join((tocheckpath,'repo')))
        os.chdir(currentwd)
        with open(os.path.join(os.getcwd(),"app","projects.json"), "w") as file: 
            json.dump(data, file)
        repo.git.add(all=True)
        repo.index.commit("initial commit")
        repo.create_head('master')
    return {'Message':returnmessage, 'space_id': space_id}

@router.put('/{space_id}/', status_code=202, tags=["Spaces"])
async def update_space(*,space_id: str = Path(None,description="space_id name"), item: SpaceModel):
    tocheckpath = str(item.storage_path)
    with open(os.path.join(os.getcwd(),"app","projects.json"), "r+")as file:
        data = json.load(file)
    for space, info in data.items():
        if space_id == space:
            toposturl = 'http://localhost:6656/apiv1/profiles/'+str(item.RO_profile)  #TODO : figure out how to not hardcode this <---
            async with ClientSession() as session:
                response = await session.request(method='GET', url=toposturl)
                print(response.status, file=sys.stderr)
                if response.status != 200:
                    raise HTTPException(status_code=400, detail="Given RO-profile does not exist")
            data[space_id]= {'storage_path':info["storage_path"],'RO_profile':item.RO_profile}
            with open(os.path.join(os.getcwd(),"app","projects.json"), "w") as file:
                json.dump(data, file)  
            return {'Data':'Update successfull'} 
    raise HTTPException(status_code=404, detail="Space not found")

@router.get('/{space_id}/fixcrate', status_code=201, tags=["Spaces"])
async def fix_crate(*,space_id: str = Path(None,description="space_id name")): 
    with open(os.path.join(os.getcwd(),"app","projects.json"), "r+") as file:
        data = json.load(file)
        try:
            toreturn = data[space_id]
            space_folder = os.sep.join((data[space_id]['storage_path'],'repo'))
            try:
                repo = git.Repo(data[space_id]['storage_path'])
            except:
                repo = git.Repo(space_folder)
        except Exception as e:
            raise HTTPException(status_code=404, detail="Space not found")
    test = complete_metadata_crate(source_path_crate=space_folder)
    repo.git.add(all=True)
    return {'Data':test} 
