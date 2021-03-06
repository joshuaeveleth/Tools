#!/usr/bin/env python
# -*- coding: utf-8 -*-
# __BEGIN_LICENSE__
#  Copyright (c) 2009-2013, United States Government as represented by the
#  Administrator of the National Aeronautics and Space Administration. All
#  rights reserved.
#
#  The NGT platform is licensed under the Apache License, Version 2.0 (the
#  "License"); you may not use this file except in compliance with the
#  License. You may obtain a copy of the License at
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# __END_LICENSE__

import sys, os, glob, optparse, re, shutil, subprocess, string, time

import IrgGeoFunctions

def man(option, opt, value, parser):
    print >>sys.stderr, parser.usage
    print >>sys.stderr, '''\
Merge the geo information with an ASU map projected CTX JP2 file.
'''
    sys.exit()

class Usage(Exception):
    def __init__(self, msg):
        self.msg = msg

#--------------------------------------------------------------------------------

# TODO: Move to IrgFileFunctions!
def replaceFileExtension(inputPath, ext):
    '''Replace the extension on a file'''
    return os.path.splitext(inputPath)[0] + ext

    
def editProjFile(projPath):
    '''Modifies a .prj file so it matches a specific format'''
    
    if not os.path.exists(projPath):
        raise Exception('isis3world.pl script failed to create required output files!')

    # Open files    
    outputPath = projPath + '.edit.prj'
    inputFile  = open(projPath,   'r')
    outputFile = open(outputPath, 'w')
    
    # Replace specific text
    for line in inputFile:
        line = line.replace('D_Mars', 'Mars')
        line = line.replace('PROJECTION["Equidistant_Cylindrical"]',
                            'PROJECTION["Equirectangular"]')
        line = line.replace('D_Mars',              'Mars')
        line = line.replace('Central_Meridian',    'central_meridian')
        line = line.replace('False_Northing',      'false_northing')
        line = line.replace('False_Easting',       'false_easting')
        line = line.replace('UNIT["Meter",1.0]',       'UNIT["meter",1.0,AUTHORITY["EPSG","9001"]]')
        if 'Standard_Parallel_1' in line:
            s1     = line.find('Standard_Parallel_1')
            s2     = line.find(',', s1)
            s3     = line.find(']', s2)
            number = line[s2+1:s3]
            line = line.replace('PARAMETER["Standard_Parallel_1",'+number+']',
                            'PARAMETER["standard_parallel_1",'+number+'],PARAMETER["latitude_of_origin",'+number+']')
        outputFile.write(line)
    
    # Clean up
    inputFile.close()
    outputFile.close()

    return outputPath
   

def addGeoDataToAsuJp2File(inputJp2Path, inputHeaderPath, outputPath, keep=False):
    """Does the actual work of adding the geo data"""

    if not os.path.exists(inputJp2Path):
        raise Exception('Input file ' + inputJp2Path + ' does not exist!')
    if not os.path.exists(inputHeaderPath):
        raise Exception('Input file ' + inputHeaderPath + ' does not exist!')


    # Get the needed paths
    prjPath = replaceFileExtension(inputJp2Path, '.prj')
    vrtPath = replaceFileExtension(inputJp2Path, '.vrt')
    
    # The perl script works best from the input folder
    originalDirectory = os.getcwd()
    print originalDirectory
    inputFolder = os.path.dirname(inputJp2Path)
    print inputFolder
    if inputFolder != '':
        os.chdir(inputFolder)

    # Call perl script, then return to original directory
    cmd = 'isis3world.pl -J -prj ' + os.path.basename(inputHeaderPath)
    print cmd
    os.system(cmd)
    if inputFolder != '':
        os.chdir(originalDirectory)

    # If the first command is not called from the input folder, need to do this
    #mv .j2w <INPUT FOLDER>/B01_009838_2108_XI_30N319W.j2w
    #mv .prj <INPUT FOLDER>/B01_009838_2108_XI_30N319W.prj

    correctedProjPath = editProjFile(prjPath)

    if (not os.path.exists(correctedProjPath)):
        raise Exception('Failed to correct proj file!')
    
    # Determine the bounds of the image in projected coordinates
    projectedBounds = IrgGeoFunctions.getProjectedBoundsFromIsisLabel(inputHeaderPath)
    projectedBoundsString = (str(projectedBounds[0]) + ' ' +
                             str(projectedBounds[3]) + ' ' +
                             str(projectedBounds[1]) + ' ' +
                             str(projectedBounds[2]) )

    # Next conversion command
    #cmd = 'gdal_translate -of VRT -a_srs ESRI::"'+ prjPath +'" -a_nodata 0  '+ inputJp2Path +' '+ vrtPath

    ## Finish the conversion
    #cmd = 'gdal_translate -of JP2OpenJPEG '+ vrtPath +' '+ outputPath
    #print(cmd)
    #os.system(cmd)
    
    # Copy the input image to the output path if different
    if (outputPath != inputJp2Path):
        cmd = 'cp '+ inputJp2Path +'  '+ outputPath
        print(cmd)
        os.system(cmd)
    
    # Add metadata to the output image, specifying a projecting string and projected coordinate boundaries.
    f = open(correctedProjPath, 'r')
    prjText=f.read()
    f.close()
    cmd = 'gdal_edit.py -mo "AREA_OR_POINT=Area"  -a_ullr ' + projectedBoundsString + ' -a_srs "'+ prjText +'"  '+ outputPath
    print(cmd)
    os.system(cmd)

    # gdal_edit.py actually puts the metadata here, the input file is not touched!
    sidecarPath = outputPath + '.aux.xml'

    # Clean up temporary files
    if not keep:
        #os.remove(vrtPath)
        os.remove(prjPath)
        os.remove(correctedProjPath)

    return (outputPath, sidecarPath)

def main():

    print '#################################################################################'
    print "Running addGeoToAsuCtxJp2.py"

    try:
        try:
            usage = "usage: addGeoToAsuCtxJp.py <inputPath> [<outputPath>] [--keep][--manual]\n  "
            parser = optparse.OptionParser(usage=usage)

            parser.set_defaults(keep=False)

            parser.add_option("--label", dest="inputHeaderFile", default="",
                              help="Path to the label file.")

            parser.add_option("--manual", action="callback", callback=man,
                              help="Read the manual.")
            parser.add_option("--keep", action="store_true", dest="keep",
                              help="Do not delete the temporary files.")
            (options, args) = parser.parse_args()
            
            if len(args) < 1:
                parser.error('Missing required input!')
            options.inputJp2Path = args[0]
            if len(args) > 1:
                options.outputPath = args[1]
            else:
                options.outputPath = inputPath # In-place correction
            
            # If the path to the header file was not provided, assume the default naming convention
            if options.inputHeaderFile == "":
                options.inputHeaderFile = replaceFileExtension(options.inputJp2Path, '.scyl.isis.hdr')
            
        except optparse.OptionError, msg:
            raise Usage(msg)

        startTime = time.time()

        (outputPath, sidecarPath) = addGeoDataToAsuJp2File(options.inputJp2Path, options.inputHeaderFile, options.outputPath, options.keep)

        print 'Created files ' + outputPath + ' and ' + sidecarPath

        endTime = time.time()

        print "Finished in " + str(endTime - startTime) + " seconds."
        print '#################################################################################'
        return 0

    except Usage, err:
        print err
        print >>sys.stderr, err.msg
        return 2

if __name__ == "__main__":
    sys.exit(main())
