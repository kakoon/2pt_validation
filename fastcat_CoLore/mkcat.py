#!/usr/bin/env python
import sys
from subs import *
sys.path=["."]+sys.path
import fastcat as fc
import numpy as np
from optparse import OptionParser
import datetime
import os

if os.environ.has_key('DESC_LSS_ROOT'):
    root=os.environ['DESC_LSS_ROOT']
else:
    root="/project/projectdirs/lsst/LSSWG"
#default in path
ipath=root+"/colore_raw"
#default out path
opath=root+"/LNMocks_staging"
#default stellar path
spath=root+"/Stars/star_table.h5"
star_zmean=0.5
star_zsigma=0.1

parser = OptionParser()
parser.add_option("--ipath", dest="ipath", default=ipath,
                  help="Path to colore output", type="string")
parser.add_option("--opath", dest="opath", default=opath,
                  help="Path to colore output", type="string")
parser.add_option("--oextra", dest="oextra", default="",
                  help="Extra string to be put in output path", type="string")
parser.add_option("--N", dest="Nr", default=10,
                  help="Number of realizations", type="int")
parser.add_option("--Nstart", dest="Nstart", default=0,
                  help="starting realization", type="int")
parser.add_option("--Ngals", dest="Ngals", default=-1,
                  help="If non-zero, subsample to this number of gals", type="int")
parser.add_option("--mpi", dest="use_mpi", default=False,
                  help="If used, use mpi4py for parallelization ",action="store_true")
parser.add_option("--Nstars", dest="Nstars", type="int",default=0,
                  help="If Nstars>0, subsample to this number of stars. If Nstars=-1 use the full stellar catalog")
parser.add_option("--stars_zmean", dest="star_zmean", type="float",default=star_zmean,
                  help="Mean 'redshift' for stars")
parser.add_option("--stars_zsigma", dest="star_zsigma", type="float",default=star_zsigma,
                  help="Sigma 'redshift' for stars")
parser.add_option("--sfile",dest='star_path',type="string", default=spath,
                  help="Input stellar catalog")
## WF and PZ options
fc.window.registerOptions(parser)
## PZ options
fc.photoz.registerOptions(parser)
## other options
parser.add_option("--realspace", dest="realspace", default=True,
                  help="Realspace instead of redshift space",action="store_true")
parser.add_option("--ztrue", dest="ztrue", default=False,
                  help="Add column with true redshift ",action="store_true")

(o, args) = parser.parse_args()

bz=np.genfromtxt(o.ipath+'/bz.txt', dtype=None, names=["z","bz"])
dNdz=np.genfromtxt(o.ipath+'/Nz.txt', dtype=None, names=["z","dNdz"])
fopath=None

## import mpi only if we actually need it
if o.use_mpi:
    from mpi4py import MPI
    comm = MPI.COMM_WORLD
    mrank = comm.Get_rank()
    mranks = "["+str(mrank)+"]:"
    msize = comm.Get_size()
    if (mrank==0):
        print "MPI Size:", msize
else:
    mrank=0
    msize=1
    mranks = ""

out_extra=""
if len(o.oextra)>0:
    out_extra+="+"+o.oextra
if (o.realspace):
    out_extra+="+realspace"
if (o.ztrue):
    out_extra+="+ztrue"
if (o.Ngals>=0):
    out_extra+="+subsamp_"+str(o.Ngals)
if(o.Nstars>0 or o.Nstars==-1):
    do_stars=True
    out_extra+="+stars_"
    if (o.Nstars>0):
        out_extra+=str(o.Nstars)
    else:
        out_extra+="all"
    stars = readStars(o.star_path, o.star_zmean, o.star_zsigma)
    print mranks, len(stars), "stars read."
else:
    do_stars=False
    
for i in range(o.Nstart,o.Nr):
    if (i%msize==mrank):
        print mranks, "Reading set ",i
        gals,inif=readColore(o.ipath+"/Set%i"%i)
        print mranks, len(gals)," galaxies read."
        if (len(gals)==0):
            print mranks, "No galaxies!"
            stop()
        # subsample if required
        if (o.Ngals>=0):
            print "Subsampling to ",o.Ngals
            # interestingly, this is superslow
            #indices=np.random.choice(xrange(len(gals)),o.Ngals, replace=False)
            # this risks repetition, but OK
            indices=np.random.randint(0,len(gals),o.Ngals)
            gals=gals[indices]
            print "Done"

        # start catalog with known dNdz and bz
        N=len(gals)
        if do_stars:
            if(len(stars)==0):
                print mranks, "No stars!"
                stop()
            try:    
                if(o.Nstars>0):
                    print "Subsampling to ",o.Nstars, " stars"
                    indices = np.random.randint(0,len(stars),o.Nstars)
                    cstars=stars[indices]
                    N=N+len(cstars)
                    gals=np.append(gals,cstars)
                else:
                    N=N+len(stars)
                    gals=np.append(gals,stars)
            except:
                print "Couldn't add stars"
                print cstars.dtype
                print gals.dtype
                raise 
                               
        meta={}
        for k,v in inif.items():
            meta['colore_'+k]=v
        meta['mkcat_git_version']=get_git_revision_short_hash()
        meta['timestamp']=str(datetime.datetime.now())
        meta['realspace']=o.realspace
        meta['command_line']=' '.join(sys.argv)
        fields=['ra','dec','z']
        if (o.ztrue):
            fields.append('z_true')
        cat=fc.Catalog(N, fields=fields,dNdz=dNdz, bz=bz,
                        meta=meta)
        cat['ra']=gals['RA']
        cat['dec']=gals['DEC']
        if (o.realspace):
            cat['z']=gals['Z_COSMO']
        else:
            cat['z']=gals['Z_COSMO']+gals['DZ_RSD']
        if (o.ztrue):
            # make a copy of z_true various PZ algos
            # will overwrite it
            cat['z_true']=cat['z']
        ## first apply window function
        print mranks, "Creating window..."
        wfunc=fc.window.getWindowFunc(o)
        print mranks, "Applying window..."
        cat.setWindow(wfunc, apply_to_data=True)
        ## next apply photoz
        pz=fc.photoz.getPhotoZ(o)
        print mranks, "Applying photoz..."
        cat.setPhotoZ(pz,apply_to_data=True)
         ## now create full output path
        if fopath is None:
            dt=datetime.datetime.now()
            daystr="%02i%02i%02i"%(dt.year-2000,dt.month,dt.day)
            fopath=o.opath+"/"+daystr+"+"+cat.photoz.NameString()+"+"+cat.window.NameString()+out_extra
            if not os.path.exists(fopath):
                os.makedirs(fopath)
        ## write the actual catalog
        fname=fopath+'/catalog%i.h5'%(i)
        print mranks, "Writing "+fname+" ..."
        cat.writeH5(fname)
if o.use_mpi:
    comm.Barrier()
