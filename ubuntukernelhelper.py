#!/usr/bin/env python

# Copyright (C) 2011, Carsten Juttner <carjay@gmx.net>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


# Simple script automating the cool method described in
# http://blog.avirtualhome.com
#


import sys
import os
import pwd
from getopt import gnu_getopt, GetoptError
import re
import shutil
import subprocess

def pexec(args, showoutput = False):
    buf = None
    res = ""
    p = subprocess.Popen(args, stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
    while buf != "":
        buf = p.stdout.read()
        if showoutput:
            sys.stdout.write(buf)
            sys.stdout.flush()
        res += buf
    p.wait()
    buf = p.stdout.read()
    if showoutput:
        sys.stdout.write(buf)
        sys.stdout.flush()
    res += buf
    return res.strip(), p.returncode


def get_arch():
    mcfgdir = os.path.join(os.getcwd(), "debian.master", "config")
    configs = []
    for x in os.listdir(mcfgdir):
        if os.path.isdir(os.path.join(mcfgdir,x)):
            configs.append(x)
    configs = sorted(configs)
    
    print("Choose config:")
    for idx, cfg in enumerate(configs):
        print("  %d: %s" % (idx+1, cfg))
    sys.stdout.write("Enter desired number: ")
    sys.stdout.flush()
    cfgidx = sys.stdin.readline()
    try:
        arch = configs[int(cfgidx)-1]
    except ValueError:
        print("invalid selection")
        return None
    
    return arch


def generate_flavour(flavourname, arch):
    currentkernel, err = pexec(['uname', '-r'])
    if err:
        print("Error reading current kernel with 'uname -r' : '%s'" % currentkernel)
        return
    
   
    srcconfig = "/boot/config-%s" % (currentkernel)
    if not os.path.exists(srcconfig):
        print("Error: unable to locate source kernel config '%s' for currently running kernel" % srcconfig)
        return
      
    mcfgdir = os.path.join(os.getcwd(), "debian.master", "config")
    destconfig = os.path.join(mcfgdir, arch, "config.flavour.%s" % flavourname)
    print("using %s kernel config to create new flavour %s" % (currentkernel, flavourname))
    shutil.copy2(srcconfig, destconfig)
    
    print("cleaning kernel dir")
    output, err = pexec(['fakeroot', 'debian/rules', 'clean'], True)
    if err:
        print("Error cleaning config")
        return

    print("updating configs")
    output, err = pexec(['fakeroot', 'debian/rules', 'updateconfigs'], True)
    if err:
        print("Error updating configs")
        return

    # here we'd usually want to edit the config which is a bit tricky
    # to do from a script, probably better to split this here somehow
    # so hand back the updated config file for further processing
    try:
        with open(destconfig, "rt") as configh:
            cfg = configh.read()
    except Exception, e:
        print("Error reading the generated config file '%s': '%s'" % (destconfig, str(e)))
        return None

    return cfg


def patch_flavour(flavourname, savedconfig, arch):
    # we need to reset the dir so build works
    # this means we have to save the generated config

    sys.stdout.write("Need to clear out the build dir, this will delete everything not committed!!!\n")
    sys.stdout.write("Are you sure (y/N)?")
    sys.stdout.flush()
    answer = sys.stdin.readline().strip().lower()
    if answer != 'y':
        print("build cancelled.")
        return
    
    output, err = pexec(['git', 'reset', '--hard'], True)
    if err:
        print("Error git-resetting")
        return
    
    output, err = pexec(['git', 'clean', '-df'], True)
    if err:
        print("Error git-cleaning")
        return
    

    print("copying back kernel config")
    mcfgdir = os.path.join(os.getcwd(), "debian.master", "config")
    kernelconfig = os.path.join(mcfgdir, arch, "config.flavour.%s" % flavourname)
    try:
        with open(kernelconfig,'wt+') as configh:
            configh.write(savedconfig)
    except Exception, e:
        print("Error writing back kernel config to '%s' : '%s'" % (kernelconfig, str(e)))
        return
    
    print("getting last abi")
    abidir = os.path.join(os.getcwd(), "debian.master", "abi")
    abientries = os.listdir(abidir)
    abis = []
    for e in abientries:
        if os.path.isdir(os.path.join(abidir, e)):
            abis.append(e)
    if len(abis) == 0:
        print("Error: empty abi directory '%s'" % abidir)
        return
    currentabi = sorted(abis)[-1]

    currentabidir = os.path.join(abidir, currentabi, arch)
    
    print("copying generic abi configs to our flavour")
    
    genericabi    = os.path.join(currentabidir, "generic")
    genericmodabi = os.path.join(currentabidir, "generic.modules")
    
    if not os.path.exists(genericabi):
        print("Error: generic abi file '%s' does not exist" % genericabi)
        return

    if not os.path.exists(genericmodabi):
        print("Error: generic abi modules file '%s' does not exist" % genericmodabi)
        return
    
    shutil.copy2(genericabi,    os.path.join(currentabidir, flavourname))
    shutil.copy2(genericmodabi, os.path.join(currentabidir, "%s.modules" % flavourname))
    
    # we need to make the build system aware or our flavours
    getabifile = os.path.join(os.getcwd(), "debian.master", "etc", "getabis")
    rulesfile = os.path.join(os.getcwd(), "debian.master", "rules.d", "%s.mk" % arch)
    varssrcfile = os.path.join(os.getcwd(), "debian.master", "control.d", "vars.generic")

    for filename, searchpattern in ( (getabifile, r'''getall\s+%s''' % arch), (rulesfile, r'''flavours.*''') ):
        try:
            print("appending flavour to %s" % filename)
            with open(filename, 'rt') as fh:
                linebuf = fh.readlines()
                
                with open(filename + '.repl', 'wb') as wh:
                    for l in linebuf:
                        if(re.match(searchpattern, l.strip())):
                            wh.write(l.strip() + " %s\n" % flavourname)
                        else:
                            wh.write(l)
                
        except Exception, e:
            print("Error appending flavour to file '%s' : '%s'" % (filename, str(e)))
            return
        shutil.move(filename + '.repl', filename)

    varsdestfile = os.path.join(os.getcwd(), "debian.master", "control.d", "vars.%s" % flavourname)
    if not os.path.exists(varssrcfile):
        print("Error: file '%s' does not exist" % varssrcfile)
        return
    shutil.copy2(varssrcfile, varsdestfile)

    print("final kernel dir clean to generate the correct debian files")
    output, err = pexec(['fakeroot', 'debian/rules', 'clean'], True)
    if err:
        print("Error cleaning config")
        return


def usage():
    print("%s [options]" % os.path.basename(sys.argv[0]))
    print("    options:")
    print("      -h, --help:")
    print("        show this help file")
    print("      -f, --flavour:")
    print("        set flavourname to use")
    

def main():
    flavourname = pwd.getpwuid(os.getuid())[0].lower().strip()
    try:
        opts, args = gnu_getopt(sys.argv[1:], 'hf:', ['help', 'flavour='])
        for opt, param in opts:
            if opt == '-h' or opt == '--help':
                usage()
                return
            elif opt == '-f' or opt == '--flavour':
                flavourname = param
            else:
                print("Error: unexpected option in command line: '%s" % opt)
                return

    except GetoptError, e:
        print ("Error parsing command line arguments: '%s'" % str(e))
        return

   
    buf, err = pexec(["lsb_release" , "-c"])
    if not err:
        m = re.match(".*Codename:\s+(.*)", buf)
        if m:
            codename, = m.groups()
        else:
            print("Unexpected result from 'lsb_release -c' :\n'%s'" % buf.strip())
            return
    else:
        print("Error getting current distribution from lsb_release:\n'%s'" % buf.strip())
        return
       
    if codename not in [ "precise" ]:
        print("Warning, untested combination")

    if "debian.master" not in os.listdir('.'):
        print("Error: script must be run in top ubuntu linux tree git directory")
        return
    
    arch = get_arch()
    if arch:
        config = generate_flavour(flavourname, arch)
        if config:
            patch_flavour(flavourname, config, arch)

    print("all patching done")
    print("you can now e.g. commit the changes:")
    print("")
    print("  git all .")
    print("  git commit -a -m \"%s modifications\"" % flavourname)
    print("")
    print("then build them:")
    print("")
    print("  skipabi=true skipmodule=true fakeroot debian/rules binary-indep")
    print("  skipabi=true skipmodule=true fakeroot debian/rules binary-perarch")
    print("  skipabi=true skipmodule=true fakeroot debian/rules binary-%s" % flavourname)
    print("")
    print("if you want to create a debug package you can do it this way:")
    print("")
    # note that skipdbg is not part of the environment because the Makefiles assume that you do not
    # want a fully blown debug package when not doing a "full_build". Setting full_build is not an
    # option since this adds targets that we do not want to build. So use a variable override here.
    print("  skipabi=true skipmodule=true fakeroot debian/rules binary-%s skipdbg=false" % flavourname)


try:
    main()
except KeyboardInterrupt:
    pass
