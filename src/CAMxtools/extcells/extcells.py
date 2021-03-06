__doc__ = r"""
.. _dumper
:mod:`dumper` -- CAMxtools dump module
============================================

... module:: extcells
    :platform: Unix, Windows
    :synopsis: It extracts indata(ntracers,nt,nz,ny,nx) at the location
               in xref and write to csv output file.
    :details:  See the description under the function.
... moduleauthor:: Jaegun Jung <jjung@ramboll.com>

"""

__all__=['extcells',]
import sys
if sys.version_info.major == 3:
    from io import BytesIO as StringIO
    commaspace = u', '
    semicolon = b';'
else:
    from StringIO import StringIO
    commaspace = ', '
    semicolon = ';'
    BrokenPipeError = None
import pandas as pd
from pandasql import sqldf
import netCDF4 as ncdf4
import os

def extcells(outfile, attr_in, tracernames, indata, xref, *, llonlat = False):
    """
    Generate csv file which has daily average values of species at the
    grid cells specified in xref file
    Arguments:
       outfile - output csv file which has daily average values at grid 
                 cells specified
       attr_in - input file attributes
       tracernames - species names to write to csv file
       indata - daily average value arrays of species used for extraction
       xref - cross reference file that specify either ij or lonlat
       llonlat - if True, xref has lonlat
    """
    # Include module
    from CAMxtools.tzone.scan_timezones import get_lcc
    from CAMxtools.tzone.scan_timezones import proj_ij_single
    import numpy as np
    import datetime
    yyyyjjj = attr_in['SDATE']
    hhmmss = attr_in['STIME']
    yyyyjjjhhmmss = yyyyjjj*1000000 + hhmmss
    tstep = attr_in['TSTEP']
    ntracers = indata.shape[0]
    nsteps   = indata.shape[1]
    nlays    = indata.shape[2]
    header_out = "ICELL JCELL YJJJ HR IJCELL LAYER".split()
    header_out.extend(tracernames)
    sites = pd.read_csv(xref, sep=',')

    # Convert lon/lat to I- and J-CELL indexes
    if llonlat:
      nx = attr_in['NCOLS']
      ny = attr_in['NROWS']
      dxy = float(attr_in['XCELL']) # Simply assume XCELL = YCELL
      lcc = get_lcc(attr_in)
      nsites = len(sites.GNAME)
      ijcells = []
      for isite in range(nsites):
        lon = sites.LON[isite]
        lat = sites.LAT[isite]
        i, j = proj_ij_single(lon, lat, dxy, lcc)
        ijcells.append(i*1000+j)
      sites['IJCELL'] = pd.Series(np.array(ijcells,dtype=int), index=sites.index)

    # Prepare data for output, data_out
    data_out=[]
    for t in range (nsteps):
        yyyyjjj = int(yyyyjjjhhmmss/1000000)
        hours = int((yyyyjjjhhmmss%1000000)/10000)
        for ijcell in sites.IJCELL.unique() :
            i = int(ijcell/1000)-1
            j = ijcell%1000-1
            trc3d = indata[:,:,:,j,i]
            for l in range (nlays):
                data_list = [i+1,j+1,int(yyyyjjj),hours,ijcell,l+1]
                data_list.extend([trc3d[s,t,l] for s in range (ntracers)])
                data_out.append(tuple(data_list))
        yyyyjjjhhmmss = int((datetime.datetime.strptime(str(yyyyjjjhhmmss),"%Y%j%H%M%S") + datetime.timedelta(days=240000/tstep)).strftime("%Y%j%H%M%S")) 
    data = pd.DataFrame.from_records(data_out, columns=header_out) #run queries

    qjoinspc = []
    for s in range (ntracers):
      if s < ntracers -1:
        qjoinspc.append("data." + tracernames[s] + ", ")
      else:
        qjoinspc.append("data." + tracernames[s])
    qjoinsites = "select data.YJJJ, data.HR, sites.GNAME, data.ICELL, data.JCELL, data.LAYER," + "".join(qjoinspc) + " from data join sites using(IJCELL)"

    data_w_sites = sqldf(qjoinsites, locals())

    data_w_sites.to_csv(outfile, index=False)

    return

def main():
    # Include functions to call
    import netCDF4 as ncdf4
    from PseudoNetCDF.camxfiles.Memmaps import uamiv
    from CAMxtools.write.set_attr import set_attr
    import numpy as np

    # Check LONLAT_IN environment variable
    llonlat = False
    try:
      ll_flag = os.environ['LONLAT_IN']
    except:
      ll_flag = 'F'
    if (ll_flag == 'T') or (ll_flag == 't') or (ll_flag == 'Y') or (ll_flag == 'y') :
      llonlat = True
    # Arguments
    outfile = str(sys.argv[1])
    infile = str(sys.argv[2])
    xref = str(sys.argv[3])

    # Open the input file
    try:
      fin = uamiv(infile)
      nt = len(fin.dimensions['TSTEP'])
    except:
      try:
        fin = ncdf4.Dataset(infile)
        nt = len(fin.dimensions['TSTEP'])
      except:
        print ("Unrecognized file type or file does not exist")
        exit ("infile = {}".format(infile))

    # Set attr_in, input file attributes
    lfin0 = True
    attr_fed = {}
    attr_in = set_attr(lfin0,fin,attr_fed)

    # Construct indata[ntracers,ny,nx]
    tracernames = list(fin.variables.keys())
    tracernames.remove('TFLAG')
    nspc = len(tracernames)
    ny = attr_in['NROWS']
    nx = attr_in['NCOLS']
    nz = attr_in['NLAYS']
    indata = np.zeros((nspc,nt,nz,ny,nx))
    for varname in tracernames:
      s = tracernames.index(varname)
      indata[s,:,:,:,:] = fin.variables[varname][:,:,:,:]

    # Extract indata[ntracers,nt,nz,ny,nx] at the location in xref and write to csv
    extcells(outfile, attr_in, tracernames, indata, xref, llonlat = llonlat)

if __name__ == '__main__':
    # For internal use (no CAMxtools package installed), set the package path.
    try :
      package_path = os.environ['PACKAGE_PATH']
      sys.path.append(package_path)
    except :
      print ("PACKAGE_PATH environment variable is not set.")

    # Main
    main()
