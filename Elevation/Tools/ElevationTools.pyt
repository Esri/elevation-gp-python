##  Copyright 2015 Esri
##   Licensed under the Apache License, Version 2.0 (the "License");
##   you may not use this file except in compliance with the License.
##   You may obtain a copy of the License at
##		http://www.apache.org/licenses/LICENSE-2.0
##   Unless required by applicable law or agreed to in writing, software
##   distributed under the License is distributed on an "AS IS" BASIS,
##   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
##   See the License for the specific language governing permissions and
##   limitations under the License.

import sys
import os
import json
import time
import arcpy

class Toolbox(object):
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the
        .pyt file)."""
        self.label = "ElevationTools"
        self.alias = "elev"

        # List of tool classes associated with this toolbox
        self.tools = [Viewshed]
        #--------------------------------------------
        #Declare data layers for publisher
        #--------------------------------------------
        if False:
            arcpy.Describe("dem30m")
            arcpy.Describe("dem60m")
            arcpy.Describe("dem90m")
            arcpy.Describe("databoundary_containment")
            arcpy.Describe("databoundary_credit")

class Viewshed(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Viewshed"
        self.description = ("Calculate viewshed for user specified observer " +
                            "locations.")
        self.canRunInBackground = False
        ### service variables
        self.visiFieldName = "Frequency"
        self.metadataFieldName = "DEMResolution"
        self.perimeterFieldName = "PerimeterKm"
        self.areaFieldName = "AreaSqKm"
        self.defaultObsOffset = 1.75
        self.defaultTargetOffset = 1.75
        self.useEarthCurvatureCorrection = True
        self.listLinearUnits = ["Meters", "Kilometers", "Feet", "Yards", "Miles"]
        #--------------------------------------------
        #Input observer point schema
        #--------------------------------------------
        self.observerSchema = r"..\Data\MD\Boundary.gdb\obs_schema"
        #--------------------------------------------
        #Output symbology
        #--------------------------------------------
        self.outputSymbology = r"..\Data\Layers\outputsymbology.lyr"
        #--------------------------------------------
        #DEM resolutions
        #--------------------------------------------
        self.dictDEMSources = {"30m":"30", "60m":"60", "90m":"90"}
        self.defaultDEMResolution = '90'
        self.defaultDEMMetadata = ["SRTM", "USGS, NASA, CGIAR", "http://www.cgiar-csi.org/"]
        #--------------------------------------------
        #Data source layers
        #--------------------------------------------
        self.dictMosaicLayers = {'30':"dem30m", '60':"dem60m", '90':"dem90m"}
        #--------------------------------------------
        #default and maximum radiuses
        #--------------------------------------------
        self.dictDefaultRadius = {'30':5000, '60':15000, '90':15000}
        self.dictMaxRadius = {'30':15000, '60':30000, '90':50000}
        self.dictMaxRadiusFinest = {'30':5000, '60':15000, '90':50000}
        self.errorMessages = ["One or more input observer points are outside of the area covered by the DEM source. Use a coarser resolution DEM or make sure all the input points are inside the DEM source.",
        "Input maximum distance exceeds the maximum value permitted. Reduce the maximum distance value or use a coarser resolution DEM.",
        "Input DEM source is not available at observer location. Select a difference DEM source.",
        "No input observer points found. The input observer features must contain at least one point.",
        "Number of input observer points exceeds the maximum number permitted. The allowed maximum number of input observer points is 25.",
        "Input units is not valid. The supported units are meters, kilometers, feet, yards and miles.",
        "Input DEM resolution {0} is not available. Select a different DEM source.",
        "Input observer feature(s) are not point shape type. Input observer features must be points.",
        "Input numeric value {0} is not valid.",
        "Input units string {0} is not valid.",
        "No DEM source was found at the observer locations. Make sure all the input points are covered by the DEM source, or use a coarser resolution DEM."]

    def getDefaultRadius(self, res):
        if not res in self.dictMosaicLayers.keys():
            arcpy.AddError(self.errorMessages[6].format(res))
            raise
            return
        return self.dictDefaultRadius[res]

    def getMaxRadius(self, res):
        if not res in self.dictMosaicLayers.keys():
            arcpy.AddError(self.errorMessages[6].format(res))
            raise
            return
        return self.dictMaxRadius[res]

    def getMaxRadiusFinest(self, res):
        if not res in self.dictMosaicLayers.keys():
            arcpy.AddError(self.errorMessages[6].format(res))
            raise
            return
        return self.dictMaxRadiusFinest[res]

    def getLayerName(self, res):
        if not res in self.dictMosaicLayers.keys():
            arcpy.AddError(self.errorMessages[6].format(res))
            raise
            return
        return self.dictMosaicLayers[res]

    def getPS(self, res):
        if not res in self.dictPS.keys():
            arcpy.AddError(self.errorMessages[6].format(res))
            raise
            return
        return self.dictPS[res]

    def getUnitConversionFactor(self, u1): # get conversion factor
        uFactor = 1
        inUnit = u1.strip().lower()
        if inUnit in ["meters", "meter"]:
            uFactor = 1
        if inUnit in ["centimeters", "centimeter"]:
            uFactor = 0.01
        if inUnit in ["decimaldegrees", "decimaldegree"]:
            arcpy.AddError(self.errorMessages[3])
            raise
        if inUnit in ["decimeters", "decimeter"]:
            uFactor = 0.1
        if inUnit in ["feet", "foot"]:
            uFactor = 0.3048
        if inUnit in ["foot_us", "feet_us"]:
            uFactor = 0.3048006096012192
        if inUnit in ["inches","inch"]:
            uFactor = 0.0254
        if inUnit in ["kilometers", "kilometer"]:
            uFactor = 1000
        if inUnit in ["miles","mile"]:
            uFactor = 1609.344
        if inUnit in ["millimeters", "millimeter"]:
            uFactor = 0.001
        if inUnit in ["nauticalmiles", "nauticalmile"]:
            uFactor = 1852
        if inUnit in ["points", "point"]:
            uFactor = 0.000352777778
        if inUnit in ["unknown", ""]:
            uFactor = 1
        if inUnit in ["yards", "yard"]:
            uFactor = 0.91440
        return uFactor

    def createBuffer(self, in_points, in_dist):
        useGCSBuffer = True
        if useGCSBuffer:
            arcpy.env.outputCoordinateSystem = 4326 # create buffer in GCS_WGS_1984
            bufferTemp = os.path.join(r"in_memory","obsbuffertemp01")
            arcpy.Buffer_analysis(in_points, bufferTemp, str(in_dist) + " Meters",
                                        "FULL", "ROUND", "NONE", "")
            arcpy.env.outputCoordinateSystem = ""

            bufferOutput = bufferTemp
        else:
            bufferOutput = os.path.join("in_memory","obsbuffertemp02")
            arcpy.Buffer_analysis(in_points, bufferOutput, str(in_dist) + " Meters",
                                        "FULL", "ROUND", "NONE", "")
        return bufferOutput

    def featureFootprintTest(self, in_features, containment_poly, test_type="contains"):
        footPrt = containment_poly
        resList = []
        if test_type.lower() == "contains":
            arcpy.SelectLayerByLocation_management(footPrt, "COMPLETELY_CONTAINS",
                                                in_features, selection_type="NEW_SELECTION")
        elif test_type.lower() == "intersect":
            arcpy.SelectLayerByLocation_management(footPrt, "INTERSECT",
                                                in_features, selection_type="NEW_SELECTION")
        else:
            pass
        with arcpy.da.SearchCursor(footPrt, ("res", "prd", "src", "srcurl", "polytype")) as cursor:
            for row in cursor:
                resList.append(row)
        return resList

    def ContainmentCheck(self, in_point_or_buffer):
        containment_layer = "databoundary_containment"
        foot_candidates = self.featureFootprintTest(in_point_or_buffer, containment_layer)
        dict_res = {}
        for t in foot_candidates:
            k1 = int(t[0])
            v1 = (t[1], t[2], t[3], t[4])
            dict_res[k1] = v1

        if len(dict_res) == 0:
            arcpy.AddError(self.errorMessages[2])
            raise
        return dict_res

    def CreditCheck(self, in_points, dem_res):
        credit_layer = "databoundary_credit"
        foot_candidates = self.featureFootprintTest(in_points, credit_layer, test_type="intersect")
        list_prd = []
        list_src = []
        list_srcurl = []
        for t in foot_candidates:
            k1 = int(t[0])
            if k1 == dem_res: # match resolution
                prd = t[1].rsplit(",")
                for p in prd:
                    if not p.strip() in list_prd:
                        list_prd.append(p.strip())
                src = t[2].rsplit(",")
                for s in src:
                    if not s.strip() in list_src:
                        list_src.append(s.strip())
                srcurl = t[3].rsplit(",")
                for u in srcurl:
                    if not u.strip() in list_srcurl:
                        list_srcurl.append(u.strip())

        prd_string = ", ".join(list_prd)
        src_string = ", ".join(list_src)
        srcurl_string = ", ".join(list_srcurl)

        credit_list = [prd_string, src_string, srcurl_string]
        #if len(list_credit) == 0:
        #    arcpy.AddError(self.errorMessages[2])
        #    raise
        return credit_list

    def validateNumerical(self, inVal, paramStr):
        if inVal == None: # None is OK
            return
        elif inVal < 0:
            arcpy.AddError(self.errorMessages[8].format(paramStr))
            raise

    def validateDistanceUnits(self, inStr, paramStr):
        tempUnitsList = [s.lower() for s in self.listLinearUnits]
        tempUnitsList.extend(["#", ""])
        if inStr == None: # None is OK
            return
        elif not (inStr.strip().lower() in tempUnitsList):
            arcpy.AddError(self.errorMessages[9].format(paramStr))
            raise

    def validateInputDEMSource(self, inDEM):
        tempDEMList = [s.upper() for s in self.dictDEMSources.keys()]
        tempDEMList.extend(["", "FINEST", "#"])
        if inDEM == None: # None is OK
            return
        elif not (inDEM.strip().upper() in tempDEMList):
            arcpy.AddError(self.errorMessages[6].format(inDEM))
            raise

    def formatInputDEMSource(self, inSource):
        tempDEMList = self.dictDEMSources.keys()
        tempDEMList.extend(["", "FINEST"])
        retVal = inSource
        for d in tempDEMList:
            if inSource.upper() == d.upper():
                retVal = d
                break
        return retVal

    def LogUsageMetering(self, taskName, numObjects, cost, startTime, values):
    	elapsed = time.time() - startTime
    	valuesMsg = taskName + json.dumps(values)

    	arcpy.AddMessage("NumObjects: {} Cost: {}".format(numObjects, cost))
    	arcpy.AddMessage(u"{0} Elapsed: {1:.3f}".format(valuesMsg, elapsed))
    	#arcpy.gp._arc_object.LogUsageMetering(5555, taskName, numObjects, cost)
    	arcpy.gp._arc_object.LogUsageMetering(7777, valuesMsg, numObjects, elapsed)

    def GetUnitsIndex(self, in_units):
        unitsIndex = 0
        listUnits = ["meters", "kilometers", "feet", "yards", "miles"]
        if in_units == None or in_units == "":
            unitsIndex = 0 # meters
        else:
            try:
                unitsIndex = listUnits.index(in_units.lower())
            except:
                unitsIndex = 0
        return unitsIndex

    def executeVisibility(self, mosaic_layer, in_points, obs_count, in_buffer, credit_list, maximum_distance,
                          dem_resolution, obs_offset1, surface_offset1,
                          generalize_output, out_viewshed_fc):

        try:

            # Buffer input point to get clip extent
            if in_buffer is None:
                bufferOutput = self.createBuffer(in_points, maximum_distance)
            else:
                bufferOutput = in_buffer

            #pixel_size = self.getPS(dem_resolution)
            arcpy.env.extent = bufferOutput
            arcpy.env.mask = bufferOutput
            arcpy.env.snapRaster = mosaic_layer
            arcpy.env.outputCoordinateSystem = 102100
            #arcpy.env.cellSize = pixel_size

            zFactor = 1
            ecc = "CURVED_EARTH"
            exeString = ("Maximum distance: " + str(maximum_distance) + " meters, DEM resolution: " + str(dem_resolution) +
                         " meters, Mosaic Layer: " + mosaic_layer + ", Observer offset: " + str(obs_offset1) +
                         ", Surface offset: " + str(surface_offset1) + ".")
            arcpy.AddMessage(exeString)
            scratchWS = "in_memory"
            outvsd0 = os.path.join(scratchWS, "viewrastmp0")
            outvsd = os.path.join(scratchWS, "viewrastmp")
            v = arcpy.gp.Visibility_sa(mosaic_layer, in_points, outvsd0, "#", "FREQUENCY", "NODATA",
                                    zFactor, ecc, "#", surface_offset1, "#", obs_offset1, "#")

            arcpy.env.extent = ""
            arcpy.env.mask = ""
            arcpy.env.snapRaster = ""
            arcpy.env.outputCoordinateSystem = ""
            arcpy.env.cellSize = ""

            # Raster to Polygon
            smoothOutput = "NO_SIMPLIFY"
            if generalize_output == True or generalize_output == "GENERALIZE":
                smoothOutput = "SIMPLIFY"
                #Generalize - remove small areas
                arcpy.gp.BoundaryClean_sa(outvsd0, outvsd)
            else:
                smoothOutput = "NO_SIMPLIFY"
                outvsd = outvsd0

            visiPolygon = r"in_memory\visipolytmp"
            arcpy.RasterToPolygon_conversion(outvsd, visiPolygon, smoothOutput, "VALUE")
            # Dissolve
            visiPolygonDisv = out_viewshed_fc  ## r"in_memory\visipolytmpdsv"
            arcpy.Dissolve_management(visiPolygon, visiPolygonDisv, "gridcode")
            # Rename gridcode
            arcpy.AddField_management(visiPolygonDisv, self.visiFieldName, "LONG")
            arcpy.CalculateField_management(visiPolygonDisv, self.visiFieldName, "!gridcode!", "PYTHON")
            arcpy.DeleteField_management(visiPolygonDisv, "gridcode")
            arcpy.AddField_management(visiPolygonDisv, self.metadataFieldName, "TEXT", field_length=50, field_alias="DEM Resolution")
            arcpy.AddField_management(visiPolygonDisv, "ProductName", "TEXT", field_length=50, field_alias="Product Name")
            arcpy.AddField_management(visiPolygonDisv, "Source", "TEXT", field_length=50, field_alias="Source")
            arcpy.AddField_management(visiPolygonDisv, "Source_URL", "TEXT", field_length=84, field_alias="Source URL")
            # Add metadata info
            dem_source = [k for k, v in self.dictDEMSources.iteritems() if v == str(dem_resolution)]
            arcpy.CalculateField_management(visiPolygonDisv, self.metadataFieldName, "'" + dem_source[0] + "'", "PYTHON")
            product_name = credit_list[0] #self.dictProductName[str(dem_resolution)]
            arcpy.CalculateField_management(visiPolygonDisv, "ProductName", "'" + product_name + "'", "PYTHON")
            source1 = credit_list[1] #self.dictSource[str(dem_resolution)]
            arcpy.CalculateField_management(visiPolygonDisv, "Source", "'" + source1 + "'", "PYTHON")
            sourceURL1 = credit_list[2] #self.dictSourceURL[str(dem_resolution)]
            arcpy.CalculateField_management(visiPolygonDisv, "Source_URL", "'" + sourceURL1 + "'", "PYTHON")
            # Add and calculate length and area field
            try:
                arcpy.AddField_management(visiPolygonDisv, self.perimeterFieldName, "DOUBLE", field_alias="Perimeter Kilometers")
                arcpy.AddField_management(visiPolygonDisv, self.areaFieldName, "DOUBLE", field_alias="Area Square Kilometers")
                arcpy.CalculateField_management(visiPolygonDisv, self.perimeterFieldName, "!shape.geodesicLength@meters! / 1000", "PYTHON")
                arcpy.CalculateField_management(visiPolygonDisv, self.areaFieldName, "!shape.geodesicArea@meters! / 1000000", "PYTHON")
            except:
                pass
            out_ras = out_viewshed_fc
            return out_ras
        except:
            msgs = arcpy.GetMessages(2)
            arcpy.AddError(msgs)
            raise
            return 0

    def getParameterInfo(self):
        """Define parameter definitions"""
        param0 = arcpy.Parameter(name="InputPoints",
                                 displayName="Input Point Features",
                                 direction="Input",
                                 parameterType="Required",
                                 datatype="GPFeatureRecordSetLayer")

        param0.value = self.observerSchema

        param1 = arcpy.Parameter(name="MaximumDistance",
                                 displayName="Maximum Distance",
                                 direction="Input",
                                 parameterType="Optional",
                                 datatype="GPDouble")
        param1.value = None

        param2 = arcpy.Parameter(name="MaximumDistanceUnits",
                                 displayName="Maximum Distance Units",
                                 direction="Input",
                                 parameterType="Optional",
                                 datatype="GPString")
        param2.filter.type = "ValueList"
        param2.filter.list = self.listLinearUnits
        param2.value = "Meters"

        param3 = arcpy.Parameter(name="DEMResolution",
                                 displayName="DEM Resolution",
                                 direction="Input",
                                 parameterType="Optional",
                                 datatype="GPString")
        param3.filter.type = "ValueList"
        list_dem = [" ", "FINEST"]
        dem_keys = self.dictDEMSources.keys()
        dem_keys.sort()
        list_dem.extend(dem_keys)
        param3.filter.list = list_dem

        param4 = arcpy.Parameter(name="ObserverHeight",
                                 displayName="Observer Height",
                                 direction="Input",
                                 parameterType="Optional",
                                 datatype="GPDouble")
        #param4.value = self.defaultObsOffset

        param5 = arcpy.Parameter(name="ObserverHeightUnits",
                                 displayName="Observer Height Units",
                                 direction="Input",
                                 parameterType="Optional",
                                 datatype="GPString")
        param5.filter.type = "ValueList"
        param5.filter.list = self.listLinearUnits
        param5.value = "Meters"

        param6 = arcpy.Parameter(name="SurfaceOffset",
                                 displayName="Surface Offset",
                                 direction="Input",
                                 parameterType="Optional",
                                 datatype="GPDouble")
        #param6.value = self.defaultTargetOffset

        param7 = arcpy.Parameter(name="SurfaceOffsetUnits",
                                 displayName="Surface Offset Units",
                                 direction="Input",
                                 parameterType="Optional",
                                 datatype="GPString")
        param7.filter.type = "ValueList"
        param7.filter.list = self.listLinearUnits
        param7.value = "Meters"

        param8 = arcpy.Parameter(name="GeneralizeViewshedPolygons",
                                 displayName="Generalize Viewshed Polygons",
                                 direction="Input",
                                 parameterType="Optional",
                                 datatype="GPBoolean")
        param8.value = True
        param8.filter.type = "ValueList"
        param8.filter.list = ["GENERALIZE", "NO_GENERALIZE"]

        param9 = arcpy.Parameter(name="OutputViewshed",
                                 displayName="Output Viewshed",
                                 direction="Output",
                                 parameterType="Derived",
                                 datatype="DEFeatureClass",
                                 symbology=self.outputSymbology)
        #param9.value = os.path.join(os.path.dirname(__file__), "Data", "viewshedout.shp")

        params = [param0, param1, param2, param3, param4,
                param5, param6, param7, param8, param9]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        try:
            startTime = time.time()

            in_points0 = parameters[0].value
            maximum_distance_p = parameters[1].value
            distance_unit = parameters[2].valueAsText
            dem_resolution_p = parameters[3].valueAsText
            obs_offset_p = parameters[4].value
            obs_offset_unit = parameters[5].valueAsText
            surface_offset_p = parameters[6].value
            surface_offset_unit = parameters[7].valueAsText
            generalize_output = parameters[8].value

            # var for metering
            maxDistanceSp = 0
            obsOffsetSp = 0
            surOffsetSp = 0
            demSourceIdx = 0

            scratchWS = "in_memory"
            out_viewshed_fc = os.path.join(scratchWS, "viewshedpoly")

            obs_offset_altered = parameters[4].altered
            arcpy.env.overwriteOutput = True

            # make a copy of the input
            in_points = "in_memory/viewshedinpnts"
            arcpy.env.outputCoordinateSystem = 4326
            arcpy.CopyFeatures_management(in_points0, in_points)
            arcpy.env.outputCoordinateSystem = ""

            # validate # of observer points specified
            gCounts = 0
            gCounts = arcpy.GetCount_management(in_points)
            pntCounts = int(gCounts.getOutput(0))
            if pntCounts < 1:
                arcpy.AddError(self.errorMessages[3])
                raise
                return
            if pntCounts > 1000: # limit of input features
                arcpy.AddError(self.errorMessages[4])
                raise
                return

            self.validateNumerical(obs_offset_p, "Observer Offset")
            self.validateNumerical(surface_offset_p, "Surface Offset")
            self.validateInputDEMSource(dem_resolution_p)

            self.validateDistanceUnits(distance_unit, "Maximum Distance Units")
            self.validateDistanceUnits(obs_offset_unit, "Observer Offset Units")
            self.validateDistanceUnits(surface_offset_unit, "Surface Offset Units")

            demSourceIdx = dem_resolution_p # metering

            if dem_resolution_p is not None and str(dem_resolution_p).upper() <> "FINEST":
                if dem_resolution_p.strip() == "":
                    dem_resolution_p = None
                if dem_resolution_p is not None:
                    dem_resolution_p = self.dictDEMSources[self.formatInputDEMSource(dem_resolution_p)]

            if obs_offset_unit == None:
                obs_offset_unit = "meters"

            if surface_offset_unit == None:
                surface_offset_unit = "meters"

            if obs_offset_p == None:
                obsOffsetSp = 0
                obs_offset = "#"
            else:
                obsOffsetSp = 1
                if obs_offset_p == 0 and obs_offset_altered == False:
                    obs_offset = "#"
                else:
                    obs_offset = obs_offset_p * self.getUnitConversionFactor(obs_offset_unit)

            if surface_offset_p == None:
                surOffsetSp = 0
                surface_offset = "#"
            else:
                surOffsetSp = 1
                surface_offset = surface_offset_p * self.getUnitConversionFactor(surface_offset_unit)

            mosaic_layer = ""

            res_dict = None
            buf_dict = None
            # case 1
            if maximum_distance_p == None and dem_resolution_p == None:
                maxDistanceSp = 0 # metering
                dem_resolution = self.defaultDEMResolution #'90'
                maximum_distance = self.getDefaultRadius(dem_resolution)
                buf1 = None
                #buf1 = self.createBuffer(in_points, maximum_distance)
                #testRes = self.bufferFootprintTest(buf1)
                testRes = [int(self.defaultDEMResolution)]
                if int(dem_resolution) in testRes:
                    pass
                else:
                    arcpy.AddError(self.errorMessages[0])
                    raise

            # case 2
            if maximum_distance_p is not None and dem_resolution_p == None:
                maxDistanceSp = 1 # metering
                maximum_distance = maximum_distance_p * self.getUnitConversionFactor(distance_unit)
                dem_resolution = self.defaultDEMResolution #'90'
                if maximum_distance > self.getMaxRadius(dem_resolution) or maximum_distance <= 0:
                    arcpy.AddError(self.errorMessages[1])
                    raise
                else:
                    buf1 = None
                    #buf1 = self.createBuffer(in_points, maximum_distance)
                    #testRes = self.bufferFootprintTest(buf1)
                    testRes = [int(self.defaultDEMResolution)]
                    if int(dem_resolution) in testRes:
                        pass
                    else:
                        arcpy.AddError(self.errorMessages[0])
                        raise

            # case 3
            if maximum_distance_p == None and str(dem_resolution_p).upper() == "FINEST":
                maxDistanceSp = 0 # metering
                res_dict = self.ContainmentCheck(in_points)
                testRes = res_dict.keys()
                if len(testRes) == 0:
                    arcpy.AddError(self.errorMessages[0])##
                    raise
                    return

                testRes.sort()
                matchFound = False
                for r1 in testRes:
                    dem_resolution = str(r1)
                    maximum_distance = self.getDefaultRadius(dem_resolution)
                    buf1 = self.createBuffer(in_points, maximum_distance)
                    buf_dict = self.ContainmentCheck(buf1)
                    bufRes = buf_dict.keys()
                    if r1 in bufRes:
                        matchFound = True
                        break
                if not matchFound:
                    arcpy.AddError(self.errorMessages[10])
                    raise

            # case 4
            if maximum_distance_p is not None and str(dem_resolution_p).upper() == "FINEST":
                maxDistanceSp = 1 # metering
                maximum_distance = maximum_distance_p * self.getUnitConversionFactor(distance_unit)
                if maximum_distance > self.getMaxRadius(self.defaultDEMResolution) or maximum_distance <= 0:
                    arcpy.AddError(self.errorMessages[1])
                    raise
                    return
                # get all resolutions available
                res_dict = self.ContainmentCheck(in_points)
                testRes = res_dict.keys()
                testRes.sort()
                # find a finest resolution with the given distance
                resl = 0
                for r1 in testRes:
                    d1 = self.getMaxRadiusFinest(str(r1))
                    if maximum_distance <= d1:
                        buf1 = self.createBuffer(in_points, maximum_distance)
                        buf_dict = self.ContainmentCheck(buf1)
                        bufRes = buf_dict.keys()
                        if r1 in bufRes:
                            resl = r1
                            break

                if resl == 0:
                    arcpy.AddError(self.errorMessages[1])##
                    raise
                    return
                else:
                    dem_resolution = str(resl)

            # case 5
            if maximum_distance_p is None and dem_resolution_p is not None and str(dem_resolution_p).upper() <> "FINEST":
                maxDistanceSp = 0 # metering
                dem_resolution = dem_resolution_p
                maximum_distance = self.getDefaultRadius(dem_resolution)
                if str(int(dem_resolution)) != self.defaultDEMResolution:
                    buf1 = self.createBuffer(in_points, maximum_distance)
                    buf_dict = self.ContainmentCheck(buf1)
                    bufRes = buf_dict.keys()
                else: # for 90m data, no need to do buffer test
                    bufRes = [int(self.defaultDEMResolution)]
                    buf1 = None
                if int(dem_resolution) in bufRes:
                    pass
                else:
                    arcpy.AddError(self.errorMessages[2])
                    raise

            # case 6
            if maximum_distance_p is not None and dem_resolution_p is not None and str(dem_resolution_p).upper() <> "FINEST":
                maxDistanceSp = 1 # metering
                dem_resolution = dem_resolution_p
                #if dem_resolution == '230':
                #    dem_resolution = '231'
                maximum_distance = maximum_distance_p * self.getUnitConversionFactor(distance_unit)
                if maximum_distance > self.getMaxRadius(dem_resolution) or maximum_distance <= 0:
                    arcpy.AddError(self.errorMessages[1])
                    raise
                else:
                    if str(int(dem_resolution)) != self.defaultDEMResolution:
                        buf1 = self.createBuffer(in_points, maximum_distance)
                        buf_dict = self.ContainmentCheck(buf1)
                        bufRes = buf_dict.keys()
                    else: # for 90m data, no need to do buffer test
                        bufRes = [int(self.defaultDEMResolution)]
                        buf1 = None
                    if int(dem_resolution) in bufRes:
                        pass
                        #arcpy.SetParameterAsText(1, outRas)
                    else:
                        arcpy.AddError(self.errorMessages[2])
                        raise

            # gather credit information
            if buf_dict is not None:
                res_dict = buf_dict

            if res_dict is None: # 90m
                credit_list = self.defaultDEMMetadata
            else:
                credit_tuple = res_dict[int(dem_resolution)]
                credit_list = []
                polytype = credit_tuple[3]
                if polytype > 0: # 1 or 2, already contains credit info
                    prd = credit_tuple[0].strip()
                    src = credit_tuple[1].strip()
                    srcurl = credit_tuple[2].strip()
                    credit_list = [prd, src, srcurl]
                else: # 0, containment only polygons, need credit check
                    credit_list = self.CreditCheck(in_points, int(dem_resolution))

            mosaic_layer = self.getLayerName(dem_resolution)
            outRas = self.executeVisibility(mosaic_layer, in_points, pntCounts, buf1, credit_list,
                                maximum_distance, dem_resolution, obs_offset, surface_offset,
                                generalize_output, out_viewshed_fc)

            arcpy.SetParameterAsText(9, out_viewshed_fc)

            # Metering
            maxDistUnitsIdx = self.GetUnitsIndex(distance_unit)
            obsOffsetUnitsIdx = self.GetUnitsIndex(obs_offset_unit)
            surOffsetUnitsIdx = self.GetUnitsIndex(surface_offset_unit)
            obsOffsetExectution = obs_offset #1.75
            surOffsetExectution = surface_offset #1.75
            generalize_out_log = 0
            if obsOffsetSp:
                obsOffsetExectution = obs_offset
            if surOffsetSp:
                surOffsetExectution = surface_offset
            if generalize_output == True or generalize_output == "GENERALIZE":
                generalize_out_log = 1

            taskName = "Viewshed"
            cost = pntCounts
            # Initiate start time
            beginTime = startTime

            values = [
                pntCounts,                # input count
                maxDistanceSp,
                maximum_distance,
                maxDistUnitsIdx,
                demSourceIdx,
                obsOffsetSp,
                obsOffsetExectution,
                obsOffsetUnitsIdx,
                surOffsetSp,
                surOffsetExectution,
                surOffsetUnitsIdx,
                generalize_out_log
                ]

            self.LogUsageMetering(taskName, 1, cost, beginTime, values)

        except Exception as err:
            import traceback
            import sys
            msgs = traceback.format_exception(*sys.exc_info())[1:]
            for msg in msgs:
                arcpy.AddMessage(msg.strip())
        except:
            arcpy.AddError("Viewshed failed to execute.")

