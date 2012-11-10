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


def main():
    if len(sys.argv) < 2:
        usage()
        return 1

    try:
        opts, args = gnu_getopt(sys.argv[1:], "sh", ["sourcetreebuild", "help"])
    except GetoptError, exc:
        print("Error parsing options: '%s'" % str(exc))
        return 1
    
    buildinsource = False
    for opt in opts:
        if opt[0] == "-s" or opt[0] == "--sourcetreebuild":
            buildinsource = True
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
    
        # layout
        for p in generated:
            if not os.path.exists(p):
                os.mkdir(p)
    
        # bootstrap
        conffile = os.path.abspath(os.path.join(gitname, 'configure'))
        if not os.path.exists(conffile):
            bootstrapfile = os.path.abspath(os.path.join(gitname, 'bootstrap'))
    
            print "Info: %s needs bootstrap" % proj
            if not os.path.exists(bootstrapfile):
                print("Error: no '%s' configure file found but no '%s' bootstrap file either" % (conffile, bootstrapfile))
                return 1
    
            cmdline = "cd %s && ./bootstrap" % (gitname)
            retval = os.system(cmdline)
            if retval != 0:
                print("Error: bootstrapping %s returned status %d" % (proj, retval))
                return 1
        else:
            print("Info: %s is already bootstrapped" % proj)
    
        # configure
        print("Info: configuring %s" % proj)
        
        envs = "LD_LIBRARY_PATH=%s/lib PKG_CONFIG_PATH=%s/lib/pkgconfig" % (prefix, prefix)
        configureoptions = get_options(proj)
        
        cmdline = "cd %s && %s --prefix=%s %s %s" % (buildname, conffile, prefix, configureoptions, envs)
        retval = os.system(cmdline)
        if retval != 0:
            print("Error: configuring %s returned status %d" % (proj, retval))
            return 1
        print("Info: finished setting up %s, cd to %s for building\n" % (proj, buildname))
    return 0


def get_options(project):
    fname = "%s.conf" % (project)
    result = []
    if os.path.exists(fname):
        try:
            with open(fname, "r") as fh:
                lines = fh.readlines()
                for l in lines:
                    if not l.strip().startswith('#'):
                        result.append(l.strip())
        except Exception, exc:
            print("Error: opening configure options file '%s' : '%s'" % (fname, str(exc)))
    return ' '.join(result)

try:
    main()
except KeyboardInterrupt:
    pass

