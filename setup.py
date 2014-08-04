import sys
import os
import glob
from distutils.core import setup, Extension
from distutils.command.build_ext import build_ext

scripts = ['corr2']
scripts = [ os.path.join('scripts',f) for f in scripts ]

sources = glob.glob(os.path.join('src','*.cpp'))

# If we build with debug, also undefine NDEBUG flag
if "--debug" in sys.argv:
    undef_macros=['NDEBUG']
else:
    undef_macros=None

copt =  {
    'gcc' : ['-fopenmp','-O3','-ffast-math'],
    'icc' : ['-openmp','-O3'],
    'clang' : ['-O3','-ffast-math'],
}
lopt =  {
    'gcc' : ['-fopenmp'],
    'icc' : ['-openmp'],
    'clang' : [],
}

def get_compiler(cc):
    """Try to figure out which kind of compiler this really is.
    In particular, try to distinguish between clang and gcc, either of which may
    be called cc or gcc.
    """
    cmd = cc + ' --version 2>&1'
    import subprocess
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
    lines = p.stdout.readlines()
    if 'clang' in lines[0]:
        # Supposedly, clang will support openmp in version 3.5.  Let's go with that for now...
        # If the version is reports >= 3.5, let's call in gcc, rather than clang to get
        # the gcc -fopenmp flag.
        line = lines[1]
        import re
        match = re.search(r'[0-9]+(\.[0-9]+)+', line)
        if match:
            version = match.group(0)
            # Get the version up to the first decimal
            # e.g. for 3.4.1 we only keep 3.4
            vnum = version[0:version.find('.')+2]
            if vnum >= '3.5':
                return 'gcc'
        return 'clang'
    elif 'gcc' in lines[0]:
        return 'gcc'
    elif 'clang' in cc:
        return 'clang'
    elif 'gcc' in cc or 'g++' in cc:
        return 'gcc'
    elif 'icc' in cc or 'icpc' in cc:
        return 'icc'
    else:
        return 'unknown'

# Make a subclass of build_ext so we can do different things depending on which compiler we have.
# In particular, we want to use different compiler options for OpenMP in each case.
# cf. http://stackoverflow.com/questions/724664/python-distutils-how-to-get-a-compiler-that-is-going-to-be-used
class my_builder( build_ext ):
    def build_extensions(self):
        cc = self.compiler.executables['compiler_cxx'][0]
        comp = get_compiler(cc)
        print 'Using compiler %s, which is %s'%(cc,comp)
        if copt.has_key(comp):
           for e in self.extensions:
               e.extra_compile_args = copt[ comp ]
        if lopt.has_key(cc):
            for e in self.extensions:
                e.extra_link_args = lopt[ comp ]
        build_ext.build_extensions(self)

ext=Extension("treecorr._treecorr",
              sources,
              undef_macros = undef_macros)

setup(name="TreeCorr", 
      version="3.0",
      description="Python module for computing 2-point correlation functions",
      license = "BSD",
      author="Mike Jarvis",
      author_email="michael@jarvis.net",
      url="https://github.com/rmjarvis/TreeCorr",
      packages=['treecorr'],
      ext_modules=[ext],
      cmdclass = {'build_ext': my_builder },
      scripts=scripts)
