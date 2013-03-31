#!/usr/bin/env python

import os
import sys
from getopt import gnu_getopt, GetoptError


def usage():
    print("Usage: %s <projectA> [<projectB>] [<options>]" % (os.path.basename(sys.argv[0])))
    print("       try to autosetup projects which use the same prefix")
    print("")
    print("       source directory must be in a directory of the same name prepended with git_")
    print("       this script will create a build dir and expects output to go into a directory")
    print("       simply called 'prefix' in the same directory")
    print("")
    print("       if a file name <proj>.conf is found in the same directory its contents will be used")
    print("       as options to configure (all lines concatenated except for those starting with '#'")
    print("       to allow comments)")
    print("")
    print("       configure is also called with LD_LIBRARY_PATH and PKG_CONFIG_PATH set to the correct")
    print("       prefix directories just in case some tools need them set up during configure")
    print("")
    print("       Example:")
    print("         configuring a project 'vlc' would try to execute a bootstrap script")
    print("         in './git_vlc', then call configure in './build_vlc' with prefix directory './prefix'")
    print("")
    print("       Options:")
    print("         -s,--sourcetreebuild")
    print("           configure build in sourcetree, for projects that do not support out-of-source tree builds")
    print("")
    print("         --no-configureenvs")
    print("           do not add variables to configure for projects that feature non-autoconf based configure scripts")



class RepoPrep:
    def __init__(self, projectname, repopath, buildpath, prefixpath, addconfigureenvs):
        self.projectname = projectname # just a fancy name
        self.repopath    = repopath    # where to find the repository for configuring
        self.buildpath   = buildpath   # where to build (can be same as repopath)
        self.prefixpath  = prefixpath  # root prefix where to put the result
        self.addconfenv  = addconfigureenvs # if True, add configure environment variables for prefix

    def prepare(self):
        '''
            requires either a "bootstrap" or "autoconf.sh" script
        '''
          
        # bootstrap
        conffile = os.path.abspath(os.path.join(self.repopath, 'configure'))
        if not os.path.exists(conffile):
            bootstrapnames = [ "bootstrap", "autogen.sh" ]
            bootstrapfile = None
            for name in bootstrapnames:
                chkpath = os.path.abspath(os.path.join(self.repopath, name))
                if os.path.exists(chkpath):
                    bootstrapfile = chkpath
                    break
   
            print "Info: %s needs bootstrap" % self.projectname
            if not bootstrapfile:
                print("Error: no '%s' configure file found but no bootstrap file (%s) either" % (conffile, ', '.join(bootstrapnames)))
                return 1
    
            # silly trick to keep configure from running through autogen.sh since we prefer out-of-source builds
            bootstrapenvs = "AUTOGEN_CONFIGURE_ARGS=\"--version\""

            cmdline = "export %s && cd %s && %s" % (bootstrapenvs, self.repopath, bootstrapfile)
            print cmdline
            retval = os.system(cmdline)
            if retval != 0:
                print("Error: bootstrapping %s returned status %d" % (self.projectname, retval))
                return 1
        else:
            print("Info: %s is already bootstrapped" % self.projectname)
    
        # configure
        print("Info: configuring %s" % self.projectname)
        
        # set path environment variable for configure (they get saved in config.status for reruns)
	envs = ""
	if self.addconfenv:
	    envs = "LD_LIBRARY_PATH=%s/lib PKG_CONFIG_PATH=%s/lib/pkgconfig" % (self.prefixpath, self.prefixpath)
        configureoptions = get_options(self.projectname)
       
        cmdline = "cd %s && %s --prefix=%s %s %s" % (self.buildpath, conffile, self.prefixpath, configureoptions, envs)
        print cmdline
        retval = os.system(cmdline)
        if retval != 0:
            print("Error: configuring %s returned status %d" % (self.projectname, retval))
            return 1
        print("Info: finished setting up %s, cd to %s for building\n" % (self.projectname, self.buildpath))



def main():
    if len(sys.argv) < 2:
        usage()
        return 1

    try:
        opts, args = gnu_getopt(sys.argv[1:], "sh", ["sourcetreebuild", "no-configureenvs", "help"])
    except GetoptError, exc:
        print("Error parsing options: '%s'" % str(exc))
        return 1
    
    buildinsource = False   # defaults
    addconfigureenvs = True

    for opt in opts:
        if opt[0] == "-s" or opt[0] == "--sourcetreebuild":
            buildinsource = True
        elif opt[0] == '--no-configureenvs':
    	    addconfigureenvs = False
        elif opt[0] == "-h" or opt[0] == "--help":
            usage()
            return 1
        else:
            print("Error: unhandled option %s" % opt[0])
            return 1

    projects = args

    for proj in projects:
        gitname = 'git_' + proj
        prefix = os.path.abspath(os.path.join(os.curdir, 'prefix'))
        generated = [ prefix ] # generated/temporary directories
        if buildinsource:
            buildname = gitname
        else:
            buildname = 'build_' + proj
            generated.append(buildname)

        print("Info: setting up %s" % proj)
    
        if not os.path.exists(gitname):
            print("Error: no source directory for project '%s' found (expected at '%s')" % (proj, os.path.abspath(gitname)))
            return 1
    
        # create temporary directories
        for p in generated:
            if not os.path.exists(p):
                os.mkdir(p)
        
        repo = RepoPrep(proj, gitname, buildname, prefix, addconfigureenvs)
        res = repo.prepare()
        if res != 0: # some error occurred (already reported by the class)
            return res
    return 0


def get_options(project):
    '''
        get options for configure (stored in <project>.conf)
    '''
    fname = "%s.conf" % (project)
    result = []
    if os.path.exists(fname):
        try:
            with open(fname, "r") as fh:
                lines = fh.readlines()
                for l in lines:
                    if not l.strip().startswith('#'): # filter out comments
                        result.append(l.strip())
        except Exception, exc:
            print("Error: opening configure options file '%s' : '%s'" % (fname, str(exc)))
    return ' '.join(result)

try:
    main()
except KeyboardInterrupt:
    pass

