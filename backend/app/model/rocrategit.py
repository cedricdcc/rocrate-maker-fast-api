import git, os, json
from abc import abstractmethod
from .location import Locations

class GitRepoCache():
    
    @staticmethod
    def repo_url_to_git_ssh_url(repo_url):
        repo_owner  = repo_url.split("github.com/")[-1].split("/")[0]
        repo_name   = repo_url.split("/")[-1].split(".git")[0]
        return("git@github.com:"+repo_owner+"/"+repo_name+".git")
    
    @staticmethod
    def clone_content(location, repo_url): 
        #  clone repo_url to location
        #  convert the repo url to a ssh url
        ssh_url = GitRepoCache.repo_url_to_git_ssh_url(repo_url=repo_url)
        git.Repo.clone_from(ssh_url, location)
    
    @staticmethod
    def update_content(location):
        # do the git stuff to clone or update
        repo = git.Repo(location)
        try:
            origin = repo.remote(name='origin')
            origin.pull()
        except Exception as e:
            return e


class RoCrateGitBase():
    
    def __init__():
        pass

    #TODO: !!!
    def find_parts(self,type_uri):
        # returns list of parts in this crate that match this type_uri
        md = self._read_metadata()
        print(type_uri)
        # run through md to find...
        # returns a set if @id that match the type url found in ro-crate-metadata.json
        # For now the function will run through the old code and get all the git urls
        toreturn = []
        print(md)
        for files_to_check in md["@graph"]:
            if(".git" in files_to_check["@id"] or "git@github.com" in files_to_check["@id"]):
                toreturn.append(files_to_check["@id"])
        return toreturn
    
    def get_object(self, subject_uri, predicate_uri):
        '''get the object from a given subject with certain predicate uri
        '''
        pass
    
    def _read_metadata(self):
        # use self.location() to extend towards ./ro-crate-metadata.json
        metadata_location = os.path.join(Locations().get_repo_location_by_url(self.repo_url),'ro-crate-metadata.json') 
        # load it and return it in some form?
        with open(metadata_location) as metadata_file:
            return(json.load(metadata_file))
        # and/or us the rocrate-py stuff

    @abstractmethod
    def location(self):
        """ returns the location of this git repo based ro crate
        """
        pass

    def sync(self):
        GitRepoCache().update_content(self.location())

    def init(self,repo_url):
        GitRepoCache().clone_content(self.location(), repo_url)