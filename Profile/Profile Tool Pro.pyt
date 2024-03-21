""" Tool name: Profile
Source name: Profile Tool.pyt
Description: Return an elevation profile for an input polyline.
Author: Environmental Systems Research Institute Inc.
Last updated: Oct. 26, 2023
"""
import os
import time
import arcpy

class Toolbox(object):
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the
        .pyt file)."""
        self.label = "Profile Tool"
        self.alias = ""

        # List of tool classes associated with this toolbox
        self.tools = [Profile]

class Profile(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Profile"
        self.description = "Return an elevation profile for an input polyline."
        self.canRunInBackground = False
        # custom properties
        self.debug = True
        self.outputToTable = False # set to True to direct the output to a table.
        self.idFieldName = "ID"
        self.glen_field1 = "proflen0"
        self.glen_field2 = "proflen1"
        self.metadataFieldName = "DEMResolution"
        self.geodesicLenFieldName = "ProfileLength"
        self.listLinearUnits = ["Meters", "Kilometers", "Feet", "Yards", "Miles"]
        #---------------------------------------------------
        # Maximum number of vertices
        #---------------------------------------------------
        self.maxNumVertices = 2000
        #---------------------------------------------------
        # DEM boundary layer
        #---------------------------------------------------
        boundaryGdbPath = r'C:\Profile\ProfileData\dembnd.gdb'
        boundaryLayer1 = os.path.join(boundaryGdbPath, "demboundary")
        if False:
            arcpy.Describe(boundaryLayer1)
        self.demBoundary = boundaryLayer1
        #----------------------------------------------------
        # Profile schema feature class
        #----------------------------------------------------
        profileSchm1 = os.path.join(boundaryGdbPath, "profileschema")
        self.profileSchema = profileSchm1
        #----------------------------------------------------
        # DEM resolution dictionary
        #---------------------------------------------------
        self.dictDEMResolutions = {"90m":"90", "30m":"30", "10m":"10"}
        self.defaultDEMResolution = '90'
        #---------------------------------------------------
        # DEM data layers
        #---------------------------------------------------
        mosaicGdbPath = r"C:\Profile\ProfileData\demdata.gdb"
        demLayer1 = os.path.join(mosaicGdbPath, "dem90m")
        demLayer2 = os.path.join(mosaicGdbPath, "dem30m")
        demLayer3 = os.path.join(mosaicGdbPath, "dem10m")
        #---------------------------------------------------
        # Wrap each variable in an arcpy.Describe statement
        #---------------------------------------------------
        if False:
            arcpy.Describe(demLayer1)
            arcpy.Describe(demLayer2)
            arcpy.Describe(demLayer3)
        #---------------------------------------------------
        # Update the DEM layers dictionary
        #---------------------------------------------------
        self.dictDEMs = {"90":demLayer1,
                        "30":demLayer2,
                        "10":demLayer3}
        #----------------------------------------------------
        # DEM coordinate system
        demSR = arcpy.Describe(list(self.dictDEMs.values())[0]).spatialReference
        self.demCoordinateSystem = demSR
        # DEM linear unit
        lun = demSR.linearUnitName
        if lun == "" or lun == None:
            lun = demSR.angularUnitName
            if 'degree' in lun.lower():
                lun = 'decimaldegrees'
        if 'foot' in lun.lower() or 'feet' in lun.lower():
            lun = 'feet'
        self.demLinearUnit = lun
        # for adjusting length, change the zf here. eg, if the DEM linear unit is feet, then zf = 0.3048.
        # for meter, zf = 1.0; for decimal degrees, use zf = 1.0
        self.zFactor = self.getUnitConversionFactor(self.demLinearUnit)

        self.errorMessages = ["No input polyline features specified. The input needs to have at list one line feature.",
                "Input resolution is not supported. Select a different DEM source.",
                "The input profile line you requested falls outside of the data currently available in this service.",
                "Input parameter {0} is not valid.",
                "The input polyline contains too many vertices. Reduce the number of vertices.",
                "The specified sample distance results in more vertices than allowed. Increase sampling distance.",
                "Input feature contains too many vertices or the sample distance is too small. Specify a line with less than 1024 vertices, or increase the sampling distance.",
                "Input sample distance cannot be 0 or negative.",
                "Input feature id field does not exist. Change to another field or leave it as default.",
                "The number of input profile lines exceeds limit. Reduce the number of input profile lines to not more than 10."]

    def getLayerName(self, res):
        if not res in self.dictDEMs.keys():
            arcpy.AddError(self.errorMessages[1])
            raise
            return
        return self.dictDEMs[res]

    def getUnitConversionFactor(self, u1): # get conversion factor
        uFactor = 1
        inUnit = u1.strip().lower()
        if inUnit in ["meters", "meter"]:
            uFactor = 1
        if inUnit in ["centimeters", "centimeter"]:
            uFactor = 0.01
        if inUnit in ["decimaldegrees", "decimaldegree"]:
            uFactor = 1
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

    def lineFootprintTest(self, in_line_features):
        # Footprint polygon
        footPrt = self.demBoundary
        resList = []
        footPrtLayer = 'aFootPrtLyr'
        arcpy.MakeFeatureLayer_management(footPrt,footPrtLayer)
        arcpy.SelectLayerByLocation_management(footPrtLayer, "COMPLETELY_CONTAINS",
                                                in_line_features)      
        with arcpy.da.SearchCursor(footPrtLayer, "res") as cursor:
            for row in cursor:
                resList.append(row[0])

        return resList

    def CountVerticesAndLength(self, in_polylines1):
        countL = 0
        countV = 0
        totalLen = 0
        individualLen = []

        list_oid = []
        list_vert = []
        list_geodesiclen = []

        with arcpy.da.SearchCursor(in_polylines1, ("Shape@", "Shape@Length", "OID@", self.glen_field2)) as cur:
            for row in cur:
                countL += 1
                countV += row[0].getPart(0).count
                totalLen += row[1]
                individualLen.append(row[1])
                list_oid.append(row[2])
                list_vert.append(row[0].getPart(0).count)
                list_geodesiclen.append(row[3])

        return (countL, countV, totalLen, individualLen, list_oid, list_vert, list_geodesiclen)

    def CountVerticesNoProjection(self, in_polylines1):
        countV = 0
        with arcpy.da.SearchCursor(in_polylines1, ("Shape@")) as cur:
            for row in cur:
                countV += row[0].getPart(0).count

        return countV

    def getResolutionByLength(self, in_len):
        dem_res = []
        if in_len < 5000:
            dem_res = [10, 30, 90]
        if in_len >= 5000 and in_len < 15000:
            dem_res = [30, 90]
        if in_len >= 15000:
            dem_res = [90]
        return dem_res

    def getResolutionByLengthFootprint(self, in_polylines, total_len):
        len_candidates = self.getResolutionByLength(total_len)
        foot_candidates = self.lineFootprintTest(in_polylines)
        foot_candidates_int = [int(x) for x in foot_candidates]
        res_list = [i for i in len_candidates if i in foot_candidates_int]
        res_list.sort()
        if len(res_list) == 0:
            arcpy.AddError(self.errorMessages[2])
            raise
        return res_list

    def getResolutionByFootprint(self, in_polylines):
        foot_candidates = self.lineFootprintTest(in_polylines)       
        foot_candidates_int = [int(x) for x in foot_candidates]
        foot_candidates_int.sort()
        if len(foot_candidates_int) == 0:
            arcpy.AddError(self.errorMessages[2])
            raise
        return foot_candidates_int

    def getDefaultNumberVertices(self, in_number_vertices):
        out_num = None
        if in_number_vertices <= 50:
            out_num = 50
        if in_number_vertices > 50 and in_number_vertices <= 200:
            out_num = 200
        if in_number_vertices > 200:
            out_num = in_number_vertices
        return out_num

    def densifyLine(self, in_line_features, distanceLU):
        if distanceLU != "": # only do it when not empty
                arcpy.Densify_edit(in_line_features, "DISTANCE", distanceLU)                

    def weedLine(self, in_line_features, in_toler):
        if in_toler != 0: # only do it when not 0
            arcpy.Generalize_edit(in_line_features, in_toler)           

    def printCoordinateSystem(self, in_dataset):
        des = arcpy.Describe(in_dataset)
        arcpy.AddMessage(des.SpatialReference.name)

    def validateNumerical(self, inVal, paramStr):
        if inVal == None: # None is OK
            return
        elif inVal <= 0:
            arcpy.AddError(self.errorMessages[7].format(paramStr))
            raise

    def validateDistanceUnits(self, inStr, paramStr):
        tempUnitsList = [s.lower() for s in self.listLinearUnits]
        tempUnitsList.extend(["#", ""])
        if inStr == None: # None is OK
            return
        elif not (inStr.lower() in tempUnitsList):
            arcpy.AddError(self.errorMessages[3].format(paramStr))
            raise

    def validateInputDEMSource(self, inDEM):
        tempDEMList = [s.upper() for s in list(self.dictDEMResolutions.keys())]
        tempDEMList.extend(["", "FINEST", "#"])
        if inDEM == None: # None is OK
            return
        elif not (inDEM.strip().upper() in tempDEMList):
            arcpy.AddError(self.errorMessages[1].format(inDEM))
            raise

    def validateFeatureIDField(self, inName, inFeature):
        fldList = arcpy.ListFields(inFeature)
        fldListLower = [f.name.lower() for f in fldList]
        if inName == None: # None is OK
            return
        elif not (inName.lower() in fldListLower):
            arcpy.AddError(self.errorMessages[8])
            raise

    def formatInputDEMSource(self, inSource):
        tempDEMList = list(self.dictDEMResolutions.keys())
        tempDEMList.extend(["", "FINEST"])
        retVal = inSource
        for d in tempDEMList:
            if inSource.upper() == d.upper():
                retVal = d
                break
        return retVal

    def createProfile(self, in_line_features, inputIsInOcean, line_id_field, idFieldIsTemp, inputSR,
            dem_resolution, line_count, list_geodesiclen, out_profile):
        try:
            line_features_inputCS = os.path.join(r"in_memory", r"linetmpafterprj03")
            route_temp = os.path.join(r"in_memory", "outroutetmp")
            interp_line_temp = r"in_memory\interpouttmp"
            out_vertices_temp = r"in_memory\verticestmp"
            arcpy.env.workspace = "in_memory"

            # get Z values from DEM
            arcpy.InterpolateShape_3d(in_surface=self.getLayerName(dem_resolution),
                                     in_feature_class=in_line_features,
                                     out_feature_class=interp_line_temp,
                                     vertices_only="VERTICES_ONLY")
            
            # Calculate M values using Create Routes tool
            # By default, M is in meters. To change the M unit,
            # change the unit in which glen_field2 is calculated (in the execute method)
            arcpy.CreateRoutes_lr(in_line_features=interp_line_temp, route_id_field=line_id_field,
                                out_feature_class=route_temp, measure_source="TWO_FIELDS",
                                from_measure_field=self.glen_field1, to_measure_field=self.glen_field2)
            
            if self.outputToTable: # out to table
                # project the line
                arcpy.env.outputCoordinateSystem = inputSR  # convert to input projection
                arcpy.CopyFeatures_management(route_temp, line_features_inputCS) # project                
                arcpy.env.outputCoordinateSystem = ""
                # extract X, Y, Z, M
                arcpy.CreateTable_management("in_memory", os.path.basename(out_profile), os.path.join(os.path.dirname(__file__), "profile_schema.dbf"))
                with arcpy.da.InsertCursor(out_profile, ("ID", "POINT_X", "POINT_Y", "POINT_M", "POINT_Z")) as icur:
                    with arcpy.da.SearchCursor(line_features_inputCS, ("Shape@", line_id_field)) as scur:
                        for row in scur:
                            geo = row[0]
                            id_val = row[1]
                            for l1 in geo.getPart():
                                for pnt in l1:
                                    x = pnt.X
                                    y = pnt.Y
                                    m = pnt.M
                                    z = pnt.Z
                                    icur.insertRow((id_val, x, y, m, z))
            else: # out to line
                # project the line
                arcpy.env.outputCoordinateSystem = inputSR  # convert to input projection
                arcpy.CopyFeatures_management(route_temp, out_profile) # project                
                arcpy.env.outputCoordinateSystem = ""
                # Add metadata info
                if inputIsInOcean:
                    dem_source = ['1000m']
                else:
                    dem_source = [k for k, v in self.dictDEMResolutions.items() if v == str(dem_resolution)]
                arcpy.AddField_management(out_profile, self.metadataFieldName, "TEXT", field_length=50, field_alias="DEM Resolution")
                arcpy.CalculateField_management(out_profile, self.metadataFieldName, "'" + dem_source[0] + "'", "PYTHON")
                # Add geodesic length for profile
                arcpy.AddField_management(out_profile, self.geodesicLenFieldName, "DOUBLE", field_alias="Length Meters")
                i = 0
                with arcpy.da.UpdateCursor(out_profile, self.geodesicLenFieldName) as ucur:
                    for row in ucur:
                        row[0] = list_geodesiclen[i]
                        i += 1
                        ucur.updateRow(row)
                # remove tempid field
                if idFieldIsTemp:
                    arcpy.DeleteField_management(out_profile, line_id_field)

        except:
            msgs = arcpy.GetMessages(2)
            arcpy.AddError(msgs)
            raise

    def getParameterInfo(self):
        """Define parameter definitions"""
        param0 = arcpy.Parameter(name="InputLineFeatures",
                                 displayName="Input Line Features",
                                 direction="Input",
                                 parameterType="Required",
                                 datatype="GPFeatureRecordSetLayer")
        # Feautre set schema
        param0.value = self.profileSchema

        param1 = arcpy.Parameter(name="ProfileIDField",
                                 displayName="Profile ID Field",
                                 direction="Input",
                                 parameterType="Optional",
                                 datatype="Field")
        param1.filter.list = ['OID', 'Short', 'Long']

        param2 = arcpy.Parameter(name="DEMResolution",
                                 displayName="DEM Resolution",
                                 direction="Input",
                                 parameterType="Optional",
                                 datatype="GPString")
        param2.filter.type = "ValueList"
        list_dem = ["FINEST"]
        dem_keys = list(self.dictDEMResolutions.keys())
        dem_keys.sort()
        list_dem.extend(dem_keys)
        param2.filter.list = list_dem

        param3 = arcpy.Parameter(name="MaximumSampleDistance",
                                 displayName="Maximum Sample Distance",
                                 direction="Input",
                                 parameterType="Optional",
                                 datatype="GPDouble")

        param4 = arcpy.Parameter(name="MaximumSampleDistanceUnits",
                                 displayName="Maximum Sample Distance Units",
                                 direction="Input",
                                 parameterType="Optional",
                                 datatype="GPString")

        param4.filter.type = "ValueList"
        param4.filter.list = self.listLinearUnits
        param4.value = "Meters"

        param5 = arcpy.Parameter(name="OutputProfile",
                                 displayName="Output Profile",
                                 direction="Output",
                                 parameterType="Derived",
                                 datatype="DEFeatureClass")

        params = [param0, param1, param2, param3, param4, param5]
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
        startTime = time.time()
        self.debug = False
        in_polylines = parameters[0].value
        profile_id_field = parameters[1].valueAsText
        dem_resolution_p = parameters[2].valueAsText
        sample_distance_p = parameters[3].value
        sample_distance_units = parameters[4].valueAsText
        out_profile = os.path.join("in_memory", "profile1")

        arcpy.env.overwriteOutput = True
        maxInputLines = 100 # sync is 100, async is 1000
        if ("elevation_gpserver" in arcpy.env.scratchWorkspace):
            maxInputLines = 1000

        # Get input SR
        d0 = arcpy.Describe(in_polylines)
        inputSR = d0.spatialReference
        oidfld1 = d0.OIDFieldName

        # project first
        polylines_after_prj = os.path.join("in_memory", "inputlinetmp02")
        # project to raster coordinate system
        arcpy.env.outputCoordinateSystem = self.demCoordinateSystem

        arcpy.CopyFeatures_management(in_polylines, polylines_after_prj) # project
        arcpy.env.outputCoordinateSystem = ""            

        # Add and calcualte geodesic length fields - from field and to field for
        # Create Routes tool to calculate the M values
        arcpy.AddField_management(polylines_after_prj, self.glen_field1, "DOUBLE")
        arcpy.CalculateField_management(polylines_after_prj, self.glen_field1,
                            "0", "PYTHON_9.3")
      
        # The unit in which glen_field2 is calculated determines the M unit.
        # To change it other units, replace meters below with desired units
        arcpy.AddField_management(polylines_after_prj, self.glen_field2, "DOUBLE")
        arcpy.CalculateField_management(polylines_after_prj, self.glen_field2,
                            "!shape.geodesiclength@meters!", "PYTHON_9.3")
      
        # validate profile id field
        time_a = time.time()
        self.validateFeatureIDField(profile_id_field, in_polylines)
        time_b = time.time()
        if self.debug:
            arcpy.AddMessage("ValidateFeatureIDField execution time: " + str(time_b - time_a))

        # make temp id field
        idFieldIsTemp = False
        temp_id_field = "tmpprflid_"
        if profile_id_field == None:
            idFieldIsTemp = True # needed for field removal later
            fieldSp = 0
            fieldIsObjID = 1
            profile_id_field = temp_id_field
        elif profile_id_field.lower() in ["oid", "fid", "objectid"]:
            idFieldIsTemp = True # needed for field removal later
            fieldSp = 1
            fieldIsObjID = 0
            profile_id_field = temp_id_field

        if profile_id_field == temp_id_field: # default
            arcpy.AddField_management(polylines_after_prj, profile_id_field, "LONG")               
            arcpy.CalculateField_management(polylines_after_prj, profile_id_field, "!" + oidfld1 + "!", "PYTHON_9.3")
            
        # var for metering
        fieldSp = 1
        fieldIsObjID = 1
        samplingDistSp = 0

        # now find the line length and number of vertices
        time_a = time.time()
        lineFact = self.CountVerticesAndLength(polylines_after_prj)
        time_b = time.time()
        if self.debug:
            arcpy.AddMessage("CountVerticesAndLength execution time: " + str(time_b - time_a))

        line_counts = lineFact[0]
        total_num_vert = lineFact[1]
        total_len = lineFact[2]
        indiv_len = lineFact[3]
        list_oid = lineFact[4]
        list_vert = lineFact[5]
        list_glen = lineFact[6]

        if line_counts < 1:
            arcpy.AddError(self.errorMessages[0])
            raise
        elif line_counts > maxInputLines:
            arcpy.AddError(self.errorMessages[9])
            raise

        self.validateNumerical(sample_distance_p, "Maximum Sample Distance")
        self.validateDistanceUnits(sample_distance_units, "Maximum Sample Distance Units")
        self.validateInputDEMSource(dem_resolution_p)

        # trim dem_resolution_p
        if dem_resolution_p is not None and str(dem_resolution_p).upper() != "FINEST":
            if dem_resolution_p.strip() == "":
                dem_resolution_p = None
            if dem_resolution_p is not None:
                dem_resolution_p = self.dictDEMResolutions[self.formatInputDEMSource(dem_resolution_p)]

        # determine whether input line is in ocean
        inputIsInOcean = False
        # determine resolution
        if str(dem_resolution_p).upper() != "FINEST":
            if dem_resolution_p is None: # case 1 blank (default)
                dem_resolution = self.defaultDEMResolution
                res_list = self.getResolutionByFootprint(polylines_after_prj)
                if not int(dem_resolution) in res_list:
                    arcpy.AddError(self.errorMessages[2])
                    raise
                    return
            else: # case 2 specified
                dem_resolution = dem_resolution_p
                res_list = self.getResolutionByFootprint(polylines_after_prj)
                if not int(dem_resolution) in res_list:
                    arcpy.AddError(self.errorMessages[2])
                    raise
                    return
        else: # case 3 - FINEST:
            res_list = self.getResolutionByFootprint(polylines_after_prj)
            dem_resolution = str(int(res_list[0]))

        if sample_distance_units == None:
            sample_distance_units = "meters"

        outfeaturelayer1 = "tempfeaturelayer"
        arcpy.MakeFeatureLayer_management(polylines_after_prj, outfeaturelayer1)          

        for oid_val in list_oid:
            query_exp = oidfld1 + "=" + str(oid_val)
            arcpy.SelectLayerByAttribute_management(outfeaturelayer1, "NEW_SELECTION", query_exp)                

            in_len = indiv_len[list_oid.index(oid_val)] # individual line length
            in_glen = list_glen[list_oid.index(oid_val)] # individual glength

            ratio1 = in_len / (in_glen / self.zFactor) # ratio to convert to Mercator
            in_num_vert = list_vert[list_oid.index(oid_val)] # individual line vertex number

            if sample_distance_p == None: # default
                samplingDistSp = 0 # metering
                out_num_vert = in_num_vert
                needDensify = False
                needWeed = False
                if in_num_vert < 50:
                    out_num_vert = 50
                    needDensify = True
                elif in_num_vert >= 50 and in_num_vert < 200:
                    out_num_vert = 200
                    needDensify = True
                elif in_num_vert >= 200 and in_num_vert <= self.maxNumVertices:
                    out_num_vert = in_num_vert
                    needDensify = False
                elif in_num_vert > self.maxNumVertices:
                    out_num_vert = self.maxNumVertices
                    needDensify = False
                    needWeed = True

                sample_distance_m = in_len / (out_num_vert - 1) # default sample distance

                if needDensify:
                    # change the unit here to DEM linear unit, eg, feet, meters, decimaldegrees
                    self.densifyLine(outfeaturelayer1, str(sample_distance_m) + " " + self.demLinearUnit)
                if needWeed:
                    self.weedLine(outfeaturelayer1, str(int(dem_resolution) / 4.0) + " " + self.demLinearUnit)
            else: # specified
                samplingDistSp = 1 # metering
                newSamplingDist = ratio1 * sample_distance_p # convert to GCS distance
                sample_distance_m = newSamplingDist * self.getUnitConversionFactor(sample_distance_units) / self.zFactor # convert to Feet
                nVert = int((in_len / sample_distance_m) + 1)
                if nVert > self.maxNumVertices:
                    arcpy.AddError(self.errorMessages[5])
                    raise
                    return
                else:
                    self.densifyLine(outfeaturelayer1, str(sample_distance_m) + " " + self.demLinearUnit)

            # final count of no. vertices
            nVert1 = self.CountVerticesNoProjection(outfeaturelayer1)
            if nVert1 > self.maxNumVertices * 2:
                arcpy.AddError(self.errorMessages[6])
                raise
                return

        # Execute the tool, line is already densified
        arcpy.AddMessage("DEM Resolution: " + dem_resolution + ", Sampling Distance: "
                           + str(sample_distance_m))
        self.createProfile(polylines_after_prj, inputIsInOcean, profile_id_field, idFieldIsTemp, inputSR,
                        dem_resolution, line_counts, list_glen, out_profile)

        arcpy.SetParameterAsText(5, out_profile)
