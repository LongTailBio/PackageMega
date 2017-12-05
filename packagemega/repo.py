import os.path
import datasuper as ds
from os import listdir, symlink
from shutil import copyfile
import sys
import inspect
from subprocess import call


class RecipeNotFoundError(Exception):
    pass


class Repo:
    repoDirName = '.package_mega'

    def __init__(self, abspath, dsRepo):
        self.abspath = abspath
        self.dsRepo = dsRepo
        self.recipeDir = os.path.join(self.abspath, 'recipes')
        self.stagingDir = os.path.join(self.abspath, 'staging')

    def addRecipes(self, uri, dev=False):
        if os.path.exists(self.uri):
            return self.addFromLocal()
        elif 'git' in self.uri:
            return self.addFromGithub()

    def addFromLocal(self, uri, dev=False):
        if uri[-9:] == 'recipe.py':
            fs = [uri]
        else:
            fs = listdir(uri)
        out = []
        for f in fs:
            if f[-9:] == 'recipe.py':
                absP = os.path.abspath(f)
                target = os.path.basename(f)
                target = os.path.join(self.recipeDir, target)
                if dev:
                    symlink(absP, target)
                else:
                    copyfile(absP, target)
                out.append(self._recipeName(f))
        return out

    def addFromGithub(self, uri):
        hname = self.uri.split('/')[-1].split('.')[0]
        dest = os.path.join(self.stagingDir, hname)
        cmd = 'git clone {} {}'.format(self.uri, dest)
        call(cmd, shell=True)
        self.addFromLocal(dest)

    def _recipeName(self, recipeFilename):
        if recipeFilename[-9:] == 'recipe.py':
            r = recipeFilename[:-9]
            if r[-1] in ['-', '_', '.']:
                r = r[:-1]
            return r
        else:
            assert False and '{} is not a recipe'.format(recipeFilename)

    def allRecipes(self):
        out = set()
        for recipe in listdir(self.recipeDir):
            try:
                r = self._recipeName(recipe)
                out.add(r)
            except AssertionError:
                pass
        return out

    def makeRecipe(self, recipeName):
        # check if we have the recipe
        # if not throw an error
        if recipeName not in self.allRecipes():
            raise RecipeNotFoundError()
        # else run it
        recipe = self._loadRecipe(recipeName)
        recipe.makeRecipe()

    def _loadRecipe(self, recipeName):
        # (sort of hacky)
        for f in listdir(self.recipeDir):
            if f[: len(recipeName)] == recipeName:
                fname = os.path.join(self.recipeDir, f)
                break
        cname = self._getClassName(fname)
        importName = os.path.basename(fname)[:-3]

        sys.path.append(os.path.dirname(fname))
        __import__(importName)
        classes = inspect.getmembers(sys.modules[importName], inspect.isclass)
        for name, c in classes:
            if name == cname:
                return c()

    def _getClassName(self, fname):
        recipeStr = open(fname).read()
        cname = None
        for line in recipeStr.split('\n'):
            if 'class' in line:
                cname = line.split()[1]
                cname = cname.split(':')[0]
                cname = cname.split('(')[0]
                break
        return cname

    def downloadDir(self):
        try:
            return os.environ['PACKAGE_MEGA_DOWNLOADS']
        except KeyError:
            try:
                defaultDatabaseDir = os.path.join(self.abspath,
                                                  'database_dir_location.txt')
                defaultDatabaseDir = open(defaultDatabaseDir).read()
                return defaultDatabaseDir
            except FileNotFoundError:
                defaultDatabaseDir = os.path.join(self.abspath, 'databases')
                return defaultDatabaseDir

    def allDatabases(self):
        out = []
        for database in self.dsRepo.db.sampleTable.getAll():
            out.append(database)
        return out

    def database(self, databaseName):
        return self.dsRepo.db.sampleTable.get(databaseName)

    def saveFiles(self, recipe, subName, *filepaths):
        with self.dsRepo as dsr:
            dsr.addSampleType('db')
            try:
                sample = dsr.sampleTable.get(recipe.name())
            except KeyError:
                sample = ds.SampleRecord(dsr,
                                         name=recipe.name(),
                                         sample_type='db')
                sample = sample.save(modify=True)

            for fType in recipe.fileTypes():
                dsr.addFileType(fType)

            fileRecs = []
            rname = '{}.{}'.format(recipe.name(), subName)
            for i, fpath in enumerate(filepaths):
                fname = '{}.{}'.format(rname, i)
                try:
                    fr = dsr.fileTable.get(fname)
                except KeyError:
                    ftype = recipe.resultSchema()[subName]
                    fr = ds.FileRecord(dsr,
                                       name=fname,
                                       filepath=fpath,
                                       file_type=ftype)
                    fr.save(modify=True)
                fileRecs.append(fname)

            schema = recipe.resultSchema()[subName]
            dsr.addResultSchema(subName, schema)
            try:
                result = dsr.resultTable.get(rname)
            except KeyError:
                result = ds.ResultRecord(dsr,
                                         name=rname,
                                         result_type=subName,
                                         file_records=fileRecs)

                result = result.save(modify=True)

            sample.addResult(result)
            sample.save(modify=True)

    @staticmethod
    def loadRepo():
        try:
            targetDir = os.environ['PACKAGE_MEGA_HOME']
        except KeyError:
            targetDir = os.environ['HOME']
        targetDir = os.path.join(targetDir, Repo.repoDirName)
        p = os.path.abspath(targetDir)
        try:
            dsRepo = ds.Repo.loadRepo(p)
        except FileNotFoundError:
            Repo._initRepo()
            return Repo.loadRepo()
        return Repo(p, dsRepo)

    @staticmethod
    def _initRepo():
        try:
            targetDir = os.environ['PACKAGE_MEGA_HOME']
        except KeyError:
            targetDir = os.environ['HOME']
        p = os.path.abspath(targetDir)
        p = os.path.join(p, Repo.repoDirName)
        os.makedirs(p)
        ds.Repo.initRepo(targetDir=p)
        r = os.path.join(p, 'recipes')
        os.makedirs(r)
        s = os.path.join(p, 'staging')
        os.makedirs(s)
        d = os.path.join(p, 'databases')
        os.makedirs(d)
