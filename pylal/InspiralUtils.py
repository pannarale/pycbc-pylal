#!/usr/bin/python
"""
Utilities for the inspiral plotting functions
"""
__version__ = "$Revision$"
__date__ = "$Date$"
__Id__ = "$Id$"

# $Source$

from glue import lal
from glue import segments
import socket, os
import sys

from glue.ligolw import utils

from glue.ligolw import lsctables


# set default color code for inspiral plotting functions
colors = {'G1':'k','H1':'r','H2':'b','L1':'g','V1':'m'}


def ErrorMessagePlotting(opts, thisplot):
   """

   """
   text = "---Error in "+opts.name+"in plotting functions "+thisplot
   if "chi" in thisplot:
     text += "\n---possible reasons related to chi-square (are you reading first stage triggers ?)"
   print >> sys.stderr, text


def message(opts, text):
  """

  """
  if opts.verbose is True:
    print text
def set_figure_name(opts, text):
  """
  return a string containing a standard output name for pylal 
  plotting functions.
  """
  fname = opts.prefix + "_"+text + opts.suffix + ".png"

  return fname


def html_write_output(opts, args, fnameList, tagLists):
  """

  """
  # -- the HTML document and output cache file
  # -- initialise the web page calling init_page
  page, extra = init_markup_page(opts)
  page.h1(opts.name + " results")
  page.hr()
  # -- filename
  html_filename = opts.prefix + opts.suffix +".html"
  html_file = file(html_filename, "w")
  # -- set output_cache properly: make sure there is a slash
  if len(opts.output_path)>1 :
    opts.output_path = opts.output_path +'/'

  for tag,fname in zip(tagLists,fnameList):
    page.a(extra.img(src=[fname], width=400, \
        alt=tag, border="2"), title=tag, href=[ fname])


  page.add("<hr/>")


  if opts.enable_output is True:
    text = writeProcessParams( opts.name, opts.version,  args)
    page.add(text)
    html_file.write(page(False))
    html_file.close()

  return html_filename

def write_output_cache(opts, html_filename,fnameList):
  """
  write the output cache file of theplotting functions
  """

  output_cache_name = opts.prefix + opts.suffix +'.cache'
#  if opts.output_path:
#    output_cache_name = opts.output_path+'/'+output_cache_name
  this = open(output_cache_name, 'w')
  if opts.enable_output is True:
    this.write(html_filename + '\n')
  for fname in fnameList:
    this.write(fname + '\n')
  this.close()


def writeProcessParams(name, version, command): 
  """
  Convert input parameters from the process params that the code was called 
  with into a formatted string that can be saved within an other document 
  (e.g., HTML)

  @param name: name of the executable/script
  @param version:version of the executable/script
  @param command: command line arguments from a pylal script
  @return text
  """
  text = "Figure(s) produced with " + name + ", " \
      + version + ", invoked with arguments:\n\n" \
      + name
  for arg in command:
    text += " " +  arg
  
  return text

def AddFileToCache(fname, cache):
  """
  Add the given file to the lal.Cache

  @param fname:
  @param cache:
  """
  file_name = fname.split('.')[0].split('-')
  cache.append(lal.CacheEntry( file_name[0], file_name[1],
    segments.segment(int(file_name[2]), 
      int(file_name[2]) + int(file_name[3])),
    'file://' + socket.gethostbyaddr(socket.gethostname())[0] + \
     os.getcwd() + '/' + fname))

def GenerateCache(fileList):
  """
  Generate a lal.Cache for the list of files

  @param fileList : a list of file
  @return cache
  """
  cache = lal.Cache()
  for file in fileList:
    AddFileToCache(file, cache)
  return(cache)


def ContentHandler(PartialLIGOLWContentHandler):
  """
  
  """
  def __init__(self, xmldoc):
    """
    New content handler that only reads in the SummValue table
    """
    def element_filter(name, attrs):
      """
      Return True if name and attrs describe a SummValueTable
      """
      return lsctables.IsTableProperties(lsctables.SummValueTable, name, attrs) 
    PartialLIGOLWContentHandler.__init__(self, xmldoc, element_filter)


def set_version(opts, name, version):
  """
  
  """
  opts.name = name
  opts.version =version

  return opts

def set_prefix_and_suffix(opts, name):
  """
  Create suffix and prefix that will be used to name the output files.

  @param opts : the user arguments (user_tag, gps_end_time and 
  gps_start_time are used).
  @param name: name of the calling function/executable
  @return prefix 
  @return suffix
  """

  # compose prefix
  prefix = name
  if opts.ifo_times:
    prefix = opts.ifo_times +"-"+ prefix
  if opts.user_tag:
    prefix = prefix + "_" + opts.user_tag
  try:
    if opts.second_stage_only is True:
      prefix = prefix + "_second_stage"
  except:
    pass
  try:
    if opts.first_stage_only is True:
      prefix = prefix + "_first_stage"
  except:
    pass
  
  if opts.output_path:
    prefix = opts.output_path+'/'+prefix

  # compose suffix
  if opts.gps_start_time and opts.gps_end_time :
    suffix = "-"+str(opts.gps_start_time)+"-"+str(opts.gps_end_time-opts.gps_start_time)
  else:
    suffix = "-unspecified-gpstime"
  opts.prefix = prefix
  opts.suffix = suffix
 
  return opts

def init_markup_page( opts):
  """
  Load the markup module, and initialise the HTML document if the opts 
  argument contains enable_ouput option.

  @param  opts : the user arguments 
  @return page 
  @return extra 
  """
  # Initialise the html output file
  if opts.enable_output is True:
    try:
      from glue import markup
      from glue.markup import oneliner as extra_oneliner
    except:
      raise ImportError("Require markup.py to generate the html page")

    page = markup.page()
    try:
      page.init(title=__title__)
    except:
      page.init()

  return page, extra_oneliner


def readFiles(fList, verbose=False):
  """
  read in the SummValueTables from a list of files

  @param fList:       list of input files
  @param verbose: True of False (default is False)
  """
  output = {}
  massOutput = {}
  count = 0
  if len(fList) == 0:
    return output

  # for each file in the list 
  for thisFile in fList:
    if verbose is True:
      print str(count)+"/"+str(len(fList))+" " + thisFile
    count = count+1
    massNum = 0
    doc = utils.load_filename(thisFile, gz = thisFile.endswith(".gz"))
    # we search for the horizon distance of a BNS (inspiral file only)
    for row in doc.childNodes[0]:
      if row.name == 'inspiral_effective_distance':
        if (row.comment == '1.40_1.40_8.00') or (row.comment == '1.4_1.4_8'):
          if not output.has_key(row.ifo):
            output[row.ifo] = lsctables.New(lsctables.SummValueTable)
          output[row.ifo].append(row)
    # and any horizon distance available (tmpltbank)
    for row in doc.childNodes[0]:
      if row.name == 'inspiral_effective_distance':
        if not massOutput.has_key(row.ifo):
          massOutput[row.ifo] = [lsctables.New(lsctables.SummValueTable)]
        if len(massOutput[row.ifo]) < massNum + 1:
          massOutput[row.ifo].append(lsctables.New(lsctables.SummValueTable))
        massOutput[row.ifo][massNum].append(row)
        massNum += 1



  return output,massOutput
