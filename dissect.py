# -*- coding: utf-8 -*-

"""
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

import sys
import os
import traceback

import jinja2
import json
import datetime
from osgeo import (gdal,
                ogr,
                osr)

from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtSql import QSqlDatabase, QSqlQuery
from qgis.core import (QgsProcessing,
                       QgsFeatureSink,
                       QgsProcessingException,
                       QgsProcessingFeatureSourceDefinition,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterVectorLayer,
                       QgsProcessingParameterString,
                       QgsProcessingParameterFile,
                       QgsProcessingParameterFileDestination,
                       QgsProcessingParameterAuthConfig,
                       QgsProcessingParameterDefinition,
                       QgsProcessingParameterBoolean,
                       QgsFeatureRequest,
                       QgsWkbTypes,
                       QgsCoordinateReferenceSystem,
                       QgsCoordinateTransform,
                       QgsCoordinateTransformContext,
                       QgsVectorLayer,
                       QgsRasterLayer,
                       QgsVectorFileWriter,
                       QgsDataSourceUri,
                       QgsProject,
                       QgsMessageLog,
                       Qgis,
                       QgsApplication,
                       QgsAuthManager,
                       QgsAuthMethodConfig
                       )

from qgis import processing
import pandas as pd
import tempfile
import time
import yaml
import re
from PyQt5.QtWidgets import QAction, QMessageBox, QProgressBar,QDockWidget,QTabWidget
from PyQt5.QtCore import *
from PyQt5.QtGui import *

# dev only
import logging

MESSAGE_CATEGORY = 'Messages'

def enable_remote_debugging(self):
    try:
        import ptvsd
        if ptvsd.is_attached():
            QgsMessageLog.logMessage("Remote Debug for Visual Studio is already active", MESSAGE_CATEGORY, Qgis.Info)
            logging.debug('Remote Debug for Visual Studio already attached')
            return
        # ptvsd.enable_attach(address=('localhost', 5678), log_dir=os.path.join(self.CONFIG_PATH, 'ptvsd_log'))
        ptvsd.enable_attach(address=('localhost', 5678))
        QgsMessageLog.logMessage("Attached remote Debug for Visual Studio", MESSAGE_CATEGORY, Qgis.Info)
        logging.debug('Attached remote Debug for Visual Studio')

    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        format_exception = traceback.format_exception(exc_type, exc_value, exc_traceback)
        QgsMessageLog.logMessage(str(e), MESSAGE_CATEGORY, Qgis.Critical)        
        QgsMessageLog.logMessage(repr(format_exception[0]), MESSAGE_CATEGORY, Qgis.Critical)
        QgsMessageLog.logMessage(repr(format_exception[1]), MESSAGE_CATEGORY, Qgis.Critical)
        QgsMessageLog.logMessage(repr(format_exception[2]), MESSAGE_CATEGORY, Qgis.Critical)
class DissectAlg(QgsProcessingAlgorithm):
    """
    Extending QgsProcessingAlgorithm class.
    """

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    AOI = 'AOI'
    XLS_CONFIG_IN = 'XLS_CONFIG_IN'
    DATABASE = 'DATABASE'
    HOST = 'HOST'
    PORT = 'PORT'
    AUTH_CONFIG = 'AUTH_CONFIG'
    OUTPUT = 'OUTPUT'
    ADD_INTERESTS = 'ADD_INTERESTS'
          
    def config(self):
        self.CONFIG_PATH = os.environ['QENV_CONFIG_PATH']
        temppath = os.environ['TEMP']

        try:
            logging.basicConfig(
            filename = os.path.join(temppath, 'dissect.log'),
            # filemode = 'w',
            encoding='utf-8',
            level=logging.DEBUG,
            format = '%(name)s - %(levelname)s - %(message)s'
            )
        except:
            feedback.pushInfo("Could not enable logging")
        
        logging.debug('|-----------------Run started at ' + datetime.datetime.now().strftime("%d%m%Y-%H-%M-%S-----------------|"))

        try:
            enable_remote_debugging(self)
        except: 
            QgsMessageLog.logMessage("Debug for VS not enabled", MESSAGE_CATEGORY, Qgis.Critical)
            

        self.SECURE_TABLES_CONFIG = os.path.join(self.CONFIG_PATH,"protected.yml")
        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&ThabReport')
        self.protected_tables = self.get_protected_tables(self.SECURE_TABLES_CONFIG)
               
        self.tool_map_layers = []
        self.failed_layers =[]

    def get_protected_tables(table,config_file):
        ''' Returns list of protected tables
        '''
        with open(config_file, 'r') as file:
            conf = yaml.safe_load(file)['protected_data']
        return conf['tables']

    def tr(self, string):
        """
        Returns a translatable string with the self.tr() function.
        """
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return DissectAlg()

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'dissect_alg'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr('dissect')

    '''
    optional script group
    '''
    # def group(self):
    #     """
    #     Returns the name of the group this algorithm belongs to. This string
    #     should be localised.
    #     """
    #     return self.tr('dissect')

    # def groupId(self):
    #     """
    #     Returns the unique ID of the group this algorithm belongs to. This
    #     string should be fixed for the algorithm, and must not be localised.
    #     The group id should be unique within each provider. Group id should
    #     contain lowercase alphanumeric characters only and no spaces or other
    #     formatting characters.
    #     """
    #     return 'dissect'

    def shortHelpString(self):
        """
        Returns a localised short helper string for the algorithm. This string
        should provide a basic description about what the algorithm does and the
        parameters and outputs associated with it..
        """
        return self.tr("dissect")
        
   

    def initAlgorithm(self, config=None):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """      
        if 'QENV_DB' not in os.environ:
            db = ''
        else:
            db = os.environ['QENV_DB']
        if 'QENV_HOST' not in os.environ:
            host = ''
        else:
            host = os.environ['QENV_HOST']
        if 'QENV_PORT' not in os.environ:
            port = ''
        else:
            port = os.environ['QENV_PORT']
        if 'QENV_XLS_CONFIG' not in os.environ:
            xls_config = ''
        else:
            xls_config = os.environ['QENV_XLS_CONFIG']
        if 'QENV_OUT' not in os.environ:
            outfile = ''
        else:
            outfile = os.environ['QENV_OUT']+'report'+datetime.datetime.now().strftime("%d%m%Y-%H-%M-%S")+".html"

        
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.AOI,
                self.tr('Area of Interest'),
                types=[QgsProcessing.TypeVectorPolygon]
            )
        )
        xl_param = QgsProcessingParameterFile(
                    name = self.XLS_CONFIG_IN,
                    description = self.tr('Input .xlsx coniguration file'),
                    optional = False,
                    extension = "xlsx",
                    defaultValue = xls_config  
                    )  
        xl_param.setFlags(xl_param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(xl_param)
        
        db_param = QgsProcessingParameterString(
                    self.DATABASE,
                    self.tr('Database'),
                    defaultValue = db,
                    optional = True
                    )
        db_param.setFlags(db_param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(db_param)

        host_param = QgsProcessingParameterString(
                    self.HOST,
                    self.tr('Host'),
                    defaultValue = host,
                    optional = True
                    )
        host_param.setFlags(host_param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(host_param)

        port_param = QgsProcessingParameterString(
                    self.PORT,
                    self.tr('Port'),
                    defaultValue = port,
                    optional = True
                    )
        port_param.setFlags(port_param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(port_param)
        
        self.addParameter(
            QgsProcessingParameterAuthConfig(
                self.AUTH_CONFIG,
                self.tr('Database authentication'),
                optional = True
            )
        )

        out_param = QgsProcessingParameterFileDestination(
                    self.OUTPUT,
                    self.tr('Report output file'),
                    'HTML files (*.html)',
                    defaultValue = outfile
                    )
        port_param.setFlags(port_param.flags() | QgsProcessingParameterDefinition.FlagIsModelOutput)
        self.addParameter(out_param)

        self.addParameter(
            QgsProcessingParameterBoolean(
                self.ADD_INTERESTS,
                self.tr('Add overlapping interests to map'),
                defaultValue = False
            )
        )


    def parse_config(self,xlsx):
        ''' parses xls into list of dictionaries 
            {'xls tab name':[{'Column1':'',
                            'Column2':'',
                            'Column3':'',
                            'Column4':''},{}]
        '''
        assert os.path.exists(xlsx)
        os.path
        data = []
        xl = pd.ExcelFile(xlsx)
        assert len(xl.sheet_names)>0, f"Problem reading excel file ({xlsx})"
        for worksheet in xl.sheet_names:
            df = xl.parse(worksheet)
            df = df.where(pd.notnull(df), None)     
            d = df.to_dict('records')
            data.append({worksheet:d})
        return data

    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """
        try:
            import ptvsd
            ptvsd.debug_this_thread()
        except:
            feedback.pushInfo("Debug for VS not enabled")

        self.config()
        logging.debug('Alg class initialized')


        # Retrieve the feature source and sink. The 'dest_id' variable is used
        # to uniquely identify the feature sink, and must be included in the
        # dictionary returned by the processAlgorithm function.
        
        aoiSource = self.parameterAsSource(parameters, 'AOI', context) # TODO do we need to use this for input w ParameterFeatureSource?
        aoi = aoiSource.materialize(QgsFeatureRequest())
        config_xls = self.parameterAsFile(parameters, 'XLS_CONFIG_IN', context)
        auth_method_id = self.parameterAsString(parameters, 'AUTH_CONFIG', context)
        output_html = self.parameterAsFileOutput(parameters, 'OUTPUT', context)
        self.add_interests = self.parameterAsBoolean(parameters, 'ADD_INTERESTS', context)
        database = self.parameterAsString(parameters, 'DATABASE', context)
        host = self.parameterAsString(parameters, 'HOST', context)
        port = self.parameterAsString(parameters, 'PORT', context)

        if feedback.isCanceled():
            feedback.pushInfo('Process cancelled by user.')
            return {}

        # TODO configure progress bar for processing 
        # see ln 187 in __init__.py for qgis_plugin for old code for message bar

        aoi_in = aoi
        xls_file = config_xls
        output = output_html
        
        # get the application's authenticaion manager
        auth_mgr = QgsApplication.authManager()
        # create an empty authmethodconfig object
        auth_cfg = QgsAuthMethodConfig()
        # load config from manager to the new config instance and decrypt sensitive data
        auth_mgr.loadAuthenticationConfig(auth_method_id, auth_cfg, True)
        # get the configuration information (including username and password)
        auth_info = auth_cfg.configMap()
        try:
            user = auth_info['username']
            password = auth_info['password']
        except:
            user = ''
            password = ''

        # TODO clean up
        '''
        I'm pretty sure if we take this route we can delete all the
        references to use_selected as aoiSource either only takes the selected
        features (or only passes on selected features during materialize()) 
        '''
        use_selected = False

        try:
            if use_selected == True and aoi_in.selectedFeatureCount()>0:
                #export to in memory layer
                aoi = processing.run("native:saveselectedfeatures", {'INPUT': aoi_in, 'OUTPUT': 'memory:'})['OUTPUT']
            else:
                ## TODO set up warning for many featured input
                # if aoi_in.featureCount()>20:
                #     msg = QMessageBox()
                #     msg.setText(f"Your area of interest ({aoi_in.name()}) contains many features")
                #     msg.setInformativeText("would you like to push the limits?")
                #     msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
                #     msg_rslt = msg.exec_()
                #     if not msg_rslt == QMessageBox.Ok:
                #         QgsMessageLog.logMessage("User initiated exit",self.PLUGIN_NAME,Qgis.Critical)
                #         return False
                aoi = aoi_in.clone()
            if aoi.sourceCrs().isGeographic:
                parameter = {'INPUT': aoi, 'TARGET_CRS': 'EPSG:3005','OUTPUT': 'memory:aoi'}
                aoi = processing.run('native:reprojectlayer', parameter)['OUTPUT']
            QgsProject.instance().addMapLayer(aoi,False)
            
            # create db object 
            oq_helper = oracle_pyqgis(database=database,host=host,port=port,user=user,password=password)

            # init report with AOI
            report_obj = report(aoi,template_path=self.CONFIG_PATH,feedback=None)

            # creates list of all fc to compare aoi too
            parsed_input = self.parse_config(xls_file)
            logging.debug(f'Config xlsx parsed successfully ({xls_file})')

            ## TODO set up progress bar
            # progress.setValue(5)
            
            # estimate the number of layers to process
            estimated_count = 0
            for t in parsed_input:
                for k in t:
                    for d in t[k]:
                        if d['Layer Name'] is not None:
                            estimated_count += 1
            i = (90 / estimated_count)
            feedback.pushInfo(f"Evaluating {estimated_count} interests")
            for tab_dict in parsed_input:
                logging.debug(f'Processing tab_dict: {tab_dict}')
                if feedback.isCanceled():
                    feedback.pushInfo('Process cancelled by user.')
                    return {}
                for key in tab_dict:
                    logging.debug(f'Processing key: {key}')
                    if feedback.isCanceled():
                        feedback.pushInfo('Process cancelled by user.')
                        return {}
                    tab = tab_dict[key]
                    for dic in tab:
                        logging.debug(f'Processing dic: {dic}')
                        if feedback.isCanceled():
                            feedback.pushInfo('Process cancelled by user.')
                            return {}
                        lyr_start = time.time()
                        layer_title = dic['Layer Name']
                        if layer_title is not None:
                            layer_title = layer_title.strip()
                            logging.debug(f'Processing layer: {layer_title}')
                            layer_subgroup = dic['Layer Group Heading']
                            layer_table = dic['Feature Class Name']
                            if layer_table is not None:
                                layer_table = layer_table.strip()
                            location = dic['Layer Source']
                            if location is not None:
                                location = location.strip()
                            layer_sql = dic['Display Query']
                            if layer_sql is None:
                                layer_sql = ''
                            layer_expansion = dic['Attribute ID']
                            feature_layer_lst = [] # build empty layer list for each obj to be merged at end of unique feature cycle
                            #QgsMessageLog.logMessage(layer_title,self.PLUGIN_NAME,Qgis.Info)
                            feedback.pushInfo('--- ' + str(layer_title) + ' ---')
                            logging.debug(f'{layer_title} location: {location}')
                            features = aoi.getFeatures()
                            for item in features: # iterate through each item in aoi
                                logging.debug(f'{layer_title} - feature item {item}')
                                if feedback.isCanceled():
                                    feedback.pushInfo('Process cancelled by user.')
                                    return {}
                                aoi.select(item.id())
                                if (location == 'BCGW'):
                                    logging.debug(f'{layer_title} - is in BCGW')
                                    assert layer_table is not None
                                    # get overlapping features
                                    has_table = oq_helper.has_table(layer_table)
                                    if has_table == True:
                                        has_spatial_rows = oq_helper.has_spatial_rows(layer_table)
                                    else:
                                        has_spatial_rows = False
                                    if has_table == True and has_spatial_rows == True:
                                        logging.debug(f'{layer_title} - table and rows confirmed')
                                        # get features from bbox
                                        selected_features = oq_helper.create_layer_anyinteract(overlay_layer=aoi,layer_name=layer_title,db_table=layer_table,sql=layer_sql)
                                        try:
                                            if selected_features.featureCount()>0:
                                                # clip them
                                                result = processing.run("native:clip", {'INPUT':selected_features, 'OVERLAY': QgsProcessingFeatureSourceDefinition(aoi.id(), True), 'OUTPUT':f'memory:{layer_title}'})['OUTPUT']
                                                if result.featureCount()>0:
                                                    feedback.pushInfo(f"{layer_title} with ({result.featureCount()}) overlapping features")
                                                    logging.debug(f"{layer_title} returned with ({result.featureCount()}) overlapping features")
                                            else:
                                                # return layer with no features
                                                result = selected_features
                                                logging.debug(f"{layer_title} returned no overlapping features")
                                        except:
                                            try:
                                                logging.debug(f"{layer_title} fixing geometry")
                                                f_layer = processing.run("native:fixgeometries", {'INPUT':selected_features,'OUTPUT':'memory:{layer_title}'})['OUTPUT']
                                                result = processing.run("native:clip", {'INPUT':f_layer, 'OVERLAY': QgsProcessingFeatureSourceDefinition(aoi.id(), True), 'OUTPUT':f'memory:{layer_title}'})['OUTPUT']
                                                logging.debug(f"{layer_title} geometry fixed and clipped")
                                            except:
                                                self.failed_layers.append(layer_title)
                                                report_obj.add_failed(layer_title, layer_subgroup, key, comment='BCGW - data/geometry issue')
                                                feedback.pushInfo(f"Error in accessing {layer_title}")
                                        if result is not None:
                                            # feedback.pushInfo(f"result type {type(result)}")
                                            # feedback.pushInfo(f"clip result count: {result.featureCount()}")
                                            feature_layer_lst.append(result)
                                            logging.debug(f"{layer_title} appended to feature_layer_lst")
                                    else:
                                        if has_table:
                                            feedback.pushInfo(f"No data in table: BCGW {layer_table}")
                                            self.failed_layers.append(layer_title)
                                            report_obj.add_failed(layer_title, layer_subgroup, key, comment='No data in table: BCGW')
                                            logging.debug(f"{layer_title} contains no rows")
                                        else:
                                            feedback.pushInfo(f"Can not access: BCGW {layer_table}")
                                            self.failed_layers.append(layer_title)
                                            report_obj.add_failed(layer_title, layer_subgroup, key, comment='Could not access on BCGW')
                                            logging.debug(f"{layer_title} could not be accessed")
                                elif (location is not None):
                                    if os.path.exists(location):
                                        logging.debug(f'{layer_title} exists, starting processing')
                                        rlayer = None
                                        vlayer = None
                                        filename, file_extension = os.path.splitext(location)
                                        if len(layer_sql)>0:
                                            location_sql = f"|subset={layer_sql}"
                                        else:
                                            location_sql = ""
                                        coverage = False
                                        if os.path.isdir(location):
                                            dir_files = os.listdir(location)
                                            for f in dir_files:
                                                if ".adf" in f:
                                                    coverage = True
                                                    break
                                        if coverage is True:
                                            # load coverage
                                            for f in os.listdir(location):
                                                if f in ['arc.adf','pal.adf','lab.adf','cnt.adf']:
                                                    vlayer = QgsVectorLayer(os.path.join(location,f), layer_title, "ogr")
                                                if f == 'hdr.adf':
                                                    rlayer = QgsRasterLayer(os.path.join(location,f),layer_title)
                                        elif file_extension in ['.shp','.kml','.kmz','.geojson']:
                                            file_location = location + location_sql
                                            vlayer = QgsVectorLayer(file_location, layer_title, "ogr")
                                            assert vlayer.isValid(),f"Failed to add {layer_title}:{filename}"
                                        elif file_extension in ['.tif']:
                                            rlayer = QgsRasterLayer(location,layer_title)
                                            assert rlayer.isValid(),f"Failed to add {layer_title}:{filename}"
                                        elif file_extension in ['.gdb','gpkg']:
                                            ogr_string = f"{location}|layername={layer_table}{location_sql}"
                                            vlayer = QgsVectorLayer(ogr_string, layer_title, "ogr")
                                        else:
                                            feedback.pushInfo(f"No loading function for {layer_title}: {location}")
                                        if vlayer is not None:
                                            logging.debug(f'{layer_title} is vector layer, starting processing')
                                            try:
                                                if vlayer.isValid():
                                                    vlayer.setSubsetString(layer_sql)
                                                    if vlayer.featureCount()>0:
                                                        logging.debug(f'{layer_title} has valid geometry')
                                                        result = processing.run("native:clip", {'INPUT':vlayer, 'OVERLAY': QgsProcessingFeatureSourceDefinition(aoi.id(), True), 'OUTPUT':f'memory:{layer_title}'})['OUTPUT']
                                                        logging.debug(f'{layer_title} clipped')
                                                    else:
                                                        feedback.pushInfo(f"Definintion Query for {layer_title}: {location} | {layer_sql}")
                                                else:
                                                    feedback.pushInfo(f"Vector layer invalid {layer_title}: {location} | {layer_table}({location_sql})")
                                            except:
                                                vlayer.setSubsetString(layer_sql)
                                                if vlayer.featureCount()>0:
                                                    logging.debug(f'{layer_title} has invalid geometry, fixing...')
                                                    f_layer = processing.run("native:fixgeometries", {'INPUT':vlayer,'OUTPUT':'memory:{layer_title}fix'})['OUTPUT']
                                                    logging.debug(f'{layer_title} geo fixed')
                                                    result = processing.run("native:clip", {'INPUT':f_layer, 'OVERLAY': QgsProcessingFeatureSourceDefinition(aoi.id(), True), 'OUTPUT':f'memory:{layer_title}'})['OUTPUT']
                                                    logging.debug(f'{layer_title} clipped')
                                                else:
                                                    feedback.pushInfo(f"Definintion Query for {layer_title}: {location} | {layer_sql}")
                                            finally:
                                                if result is not None:
                                                    feature_layer_lst.append(result)
                                                    logging.debug(f'{layer_title} added to feature_layer_lst')
                                                    feedback.pushInfo(f"{layer_title}: {result.featureCount()} overlapping features found")
                                        elif rlayer is not None:
                                            enable_raster = False
                                            # work below for feature to report on raster layers. This is disabled and
                                            # TODO: build raster classification algorithm
                                            if enable_raster is False:
                                                print ("Raster processing is not yet supported/enabled")
                                            if enable_raster:
                                                print ("Starting Raster process")
                                                # clp_raster = processing.run("gdal:cliprasterbymasklayer", 
                                                #     {'INPUT':rlayer,
                                                #     'MASK':QgsProcessingFeatureSourceDefinition(aoi.id(), True),
                                                #     'SOURCE_CRS':QgsCoordinateReferenceSystem('EPSG:3005'),
                                                #     'TARGET_CRS':QgsCoordinateReferenceSystem('EPSG:3005'),
                                                #     'NODATA':None,
                                                #     'ALPHA_BAND':False,
                                                #     'CROP_TO_CUTLINE':True,
                                                #     'KEEP_RESOLUTION':False,
                                                #     'SET_RESOLUTION':False,
                                                #     'X_RESOLUTION':None,'Y_RESOLUTION':None,
                                                #     'MULTITHREADING':False,
                                                #     'OPTIONS':'',
                                                #     'DATA_TYPE':0,
                                                #     'EXTRA':'',
                                                #     'OUTPUT':'TEMPORARY_OUTPUT'})['OUTPUT']
                                                clp_raster = self.gdal_raster_clip(rlayer,aoi)
                                                dbf = location + ".vat.dbf"
                                                vlookup = {}
                                                if os.path.exists(dbf):
                                                    dbfdriver = ogr.GetDriverByName("ESRI Shapefile")
                                                    dbfdatasource = dbfdriver.Open(dbf,0)
                                                    dbflayer = dbfdatasource.GetLayer()
                                                    dbflayer_def = dbflayer.GetLayerDefn()
                                                    fields = [dbflayer_def.GetFieldDefn(i).GetName() for i in range(dbflayer_def.GetFieldCount())]
                                                    assert value_field in fields
                                                    for f in dbflayer:
                                                        vlookup[f.GetField('VALUE')]= f.GetField(value_field)
                                                # This gdal:polygonize seems to be an issue in QGIS <= 3.22 hopefully fixed at a later date
                                                # vector = processing.run("gdal:polygonize", 
                                                #     {'INPUT':clp_raster,'BAND':1,'FIELD':'DN','EIGHT_CONNECTEDNESS':False,
                                                #     'EXTRA':'','OUTPUT':'TEMPORARY_OUTPUT'})
                                                # Work around below uses gdal directly
                                                shp = self.gdal_polygonize(clp_raster)
                                                shp_vlayer = QgsVectorLayer(shp, layer_title, "ogr")
                                                # end workaround
                                                if len(vlookup)>0:
                                                    field_length = len(max(vlookup.values()))
                                                    vector = processing.run("native:addfieldtoattributestable", 
                                                        {'INPUT':shp_vlayer,
                                                        'FIELD_NAME':value_field,
                                                        'FIELD_TYPE':2,
                                                        'FIELD_LENGTH':field_length,
                                                        'FIELD_PRECISION':0,
                                                        'OUTPUT':'TEMPORARY_OUTPUT'})['OUTPUT']
                                                    findex = vector.fields().indexFromName(value_field)
                                                    assert findex != -1
                                                    for feat in vector.getFeatures():
                                                        vector.changeAttributeValue(feat.id(),findex,vlookup[feat['DN']])
                                                    vector.commitChanges()
                                                else:
                                                    value_field = 'DN'
                                                    vector = shp_vlayer
                                                if (re.search(r'\bValue\b', layer_sql) or re.search(r'\bValue\b', layer_sql)):
                                                    layer_sql = layer_sql.replace("VALUE ","DN").replace("Value ","DN")
                                                if len(layer_sql)>0:
                                                    vector.setSubsetString(layer_sql)
                                                if vector.featureCount()>0:
                                                    result = vector
                                                else:
                                                    result = None
                                                # end raster processing
                                                # QgsMessageLog.logMessage("No raster summary function",self.PLUGIN_NAME,Qgis.Warning)

                                            if result is not None:
                                                feature_layer_lst.append(result)
                                                
                                    else:
                                        # os.path.exists(location) == False
                                        feedback.pushInfo(f"Can not make valid: {location}")
                                        self.failed_layers.append(layer_title)
                                        report_obj.add_failed(layer_title, layer_subgroup, key, comment='Not a valid file path')

                                aoi.removeSelection()

                            # TODO understand this - it is only for BCGW? (or raster) why?
                            if len(feature_layer_lst) > 0:
                                logging.debug(f'{layer_title} Merging feature_layer_lst, length: {len(feature_layer_lst)}')
                                try:
                                    if len(feature_layer_lst)>1:
                                        result = processing.run("native:mergevectorlayers", {'LAYERS':feature_layer_lst, 'CRS':QgsCoordinateReferenceSystem('EPSG:3005'),'OUTPUT':f'memory:{layer_title}'})['OUTPUT']
                                        result.setCrs(QgsCoordinateReferenceSystem('EPSG:3005'),True)
                                    else:
                                        result = feature_layer_lst[0]
                                    if result.crs().authid() != 'EPSG:3005':
                                        result = processing.run('native:reprojectlayer', {'INPUT': result, 'TARGET_CRS': 'EPSG:3005', 'OUTPUT': f'memory:{layer_title}'})['OUTPUT']
                                    idx = result.fields().indexFromName( 'SE_ANNO_CAD_DATA' )
                                    if idx != (-1):
                                        res = result.dataProvider().deleteAttributes([idx])
                                        result.updateFields()
                                except:
                                    feedback.pushInfo(f"Could not merge results for {layer_title}")
                            
                            # test new report
                            if (layer_expansion is None):
                                layer_expansion = ''
                            if len(layer_expansion)>0:
                                # summary_fields = layer_expansion.split(',')
                                summary_fields = [f.strip() for f in layer_expansion.split(',')]
                            else:
                                summary_fields = []
                            try:
                                delta_time = round(time.time()-lyr_start,1)
                                feedback.pushInfo(f"{layer_title}: {delta_time} seconds")
                                logging.debug(f'{layer_title}: {delta_time} seconds to process')
                                if result is not None:      
                                    if result.featureCount()>0:
                                        if self.add_interests is True:
                                            logging.debug(f'{layer_title}: adding to map')
                                            QgsProject.instance().addMapLayer(result)
                                            self.tool_map_layers.append(result.id())
                                            logging.debug(f'{layer_title}: added to map')
                                    if layer_table not in self.protected_tables:
                                        report_obj.add_interest(result,key,layer_subgroup,summary_fields,secure=False)
                                        logging.debug(f'{layer_title}: added to report (non-secure)')
                                    else:
                                        report_obj.add_interest(result,key,layer_subgroup,summary_fields,secure=True)
                                        logging.debug(f'{layer_title}: added to report (secure)')
                                ## TODO progress bar
                                # p = progress.value()
                                # progress.setValue(p+i)
                            except:
                                feedback.pushInfo(f"Failed to add {layer_title} to map/report")
                                logging.error(f'{layer_title}: failed to add to map/report')
                            finally:
                                result = None

            # write report
            result = report_obj.report(output)
            logging.debug('Report produced')
            # clean up
            QgsProject.instance().removeMapLayer(aoi.id())
            report_obj = None
            del oq_helper
            logging.debug('Clean up complete')
            feedback.pushInfo(f"Failed layers: {self.failed_layers}")
            result_msg = {}
            result_msg[self.OUTPUT] = output
            return result_msg

        except Exception as e:
            # clean up
            QgsProject.instance().removeMapLayer(aoi.id())
            for lyr_id in self.tool_map_layers:
                QgsProject.instance().removeMapLayer(lyr_id)
            report_obj = None
            del oq_helper
            raise QgsProcessingException(sys.exc_info())
            

        '''
        TODO remove
        
        stuff below here in processingAlgorithm class is from template and likely
        must be deleted
        '''
       
        # # Compute the number of steps to display within the progress bar and
        # # get features from source
        # total = 100.0 / aoi.featureCount() if aoi.featureCount() else 0
        # features = aoi.getFeatures()

        #     # Update the progress bar
        #     feedback.setProgress(int(current * total))
   
class report:
    ''' Class report includes parameters to track attributes of interests and
        methods to generate a report
        initialized with QgsVectorLayer descibing report area of interest
        self.interests dictionary
        {
            name:'',
            field_summary: {},
            geom_type:''
            area/length:0.0,
            count:0,
            geojson:'filepath'
        }
    '''
    # import ptvsd
    # ptvsd.debug_this_thread()

    TEMPLATE_RELATIVE_PATH = 'templates'

    def __init__(self,aoi,template_path,feedback):
        self.fb = feedback
        assert os.path.exists(os.path.join(template_path,self.TEMPLATE_RELATIVE_PATH))
        self.template_path = template_path
        self.interests = []
        self.aoi = self.aoi_info(aoi)
        self.aoi_layer = aoi # TODO remove? never used?
        self.failedLyrs = []
        
    def aoi_info(self,aoi):
        '''prepars key:value dict with keys name,area,geojson
        aoi: QgsVectorLayer'''
        a = 0.0
        if isinstance(aoi, QgsVectorLayer) is False:
            return None
        if aoi.selectedFeatureCount()>0:
            features = aoi.selectedFeatures()
        else:
            features = aoi.getFeatures()
        for f in features:
            geom = f.geometry()
            geom_type = QgsWkbTypes.displayString(geom.wkbType())
            assert geom_type in ['Polygon','MultiPolygon','Polygon25D','MultiPolygonZ'], "Area of interestest must be polygonal"
            a += geom.area()
        geojson = self.vectorlayer_to_geojson(aoi)
        centroid = self.get_layer_center(aoi,4326)
        name = aoi.name()
        d = {'name':name,'area':a,'centerLatLong':centroid,'geojson':geojson}
        return d

    def get_layer_center(self,layer,to_epsg_cd):
        """ returns Lat,Long string"""
        r_layer = processing.run('native:reprojectlayer', {'INPUT': layer, 'TARGET_CRS': 'EPSG:{}'.format(to_epsg_cd), 'OUTPUT': 'memory:{}'.format(layer.name())})['OUTPUT']
        center = r_layer.extent().center()
        return str(center.y()) +', '+ str(center.x())

    def add_interest(self,intersected_layer,group, subgroup,summary_fields, secure):
        ''' add an interest to the report
            parameters: interested_layer
        '''
        
        interest = {'name':intersected_layer.name(),
            'group':group,
            'subgroup':subgroup}
        logging.debug(f'Building report: adding interest {interest}')
        fieldNames = [field.name() for field in intersected_layer.fields()]
        summary_dict = {}
        d = {'count':0,'length':0.0,'area':0.0}
        for f in intersected_layer.getFeatures():
            geom = f.geometry()
            geom_type = QgsWkbTypes.displayString(geom.wkbType())
            interest['geometry_type'] = geom_type
            
            if (geom_type in ['Point','MultiPoint']):
                d['count'] += 1
            elif (geom_type in ['Polygon','MultiPolygon','MultiPolygonZ']):             
                d['count'] += 1
                a = geom.area()
                d['area'] += a

            elif (geom_type in ['LineString','MultiLineString','MultiLineStringZ']):
                d['count'] += 1
                l = geom.length()
                d['length'] += l
            else:
                logging.error(f"Unexpected geometry type:{geom_type} during add_interest")
                raise Exception (f"Unexpected geometry type:{geom_type}")
            value_merge = []
            for sf in summary_fields:
                assert sf in fieldNames, f"summary field ({sf}) does not exist in layer({intersected_layer.name()})"
                value = f[sf]
                if isinstance(value, QDateTime): # convert QDateTime to formatted string
                    value=value.toPyDateTime().date().isoformat()
                else:
                    value = str(value)
                value_merge.append(value)
            if len(value_merge)>0:
                value_string =" | ".join(value_merge)
                field_string =" | ".join(summary_fields)

                # add metrics
                if value_string not in summary_dict.keys():
                    summary_dict[value_string] = {'count':0,'value':0,'unit':''}
                if geom_type in ['Point','MultiPoint']:
                    summary_dict[value_string]['count'] +=1
                elif geom_type in ['LineString','MultiLineString']:
                    summary_dict[value_string]['count'] +=1
                    summary_dict[value_string]['value']+=geom.length()
                    summary_dict[value_string]['unit']='m'
                elif geom_type in ['Polygon','MultiPolygon']:
                    summary_dict[value_string]['count'] +=1
                    summary_dict[value_string]['value']+=geom.area()/10000
                    summary_dict[value_string]['unit']='ha'
            else:
                field_string=''
        
        if (d['area']>0):
            interest['value'] = d['area']/10000
            interest['unit'] = 'ha'
        elif (d['length']>0):
            interest['value'] = d['length']
            interest['unit'] = 'm'
        if 'count' in d.keys():
            interest['count'] = d['count']
        else:
            interest['count']=0
        if intersected_layer.featureCount() > 0:
            summary = []
            interest['field_summary'] = summary_dict
            interest['field_names_summary'] = field_string
            if secure is True:
                interest['geojson'] = None   
            else: 
                logging.debug(f'Exporting {intersected_layer} to geojson')
                interest['geojson'] = self.vectorlayer_to_geojson(intersected_layer)
                logging.debug('Exported to geojson, geojson returned')
        else:
            interest['geojson'] = None
            interest['field_summary'] = []
        self.interests.append(interest)
        logging.debug('Interest appended to interests')
    def vectorlayer_to_geojson(self,layer):
        '''Export QgsVectorlayer to temp geojson'''
        file_name = layer.name().replace(' ','_').replace('.','_') + ".geojson"
        file_name = file_name.replace('/','_')
        file_name = file_name.replace('\\','_')
        logging.debug('V2GEOJSON: geojson name built')
        temp_path = os.environ['TEMP']
        geojson_path = os.path.join(temp_path,file_name)
        logging.debug('V2GEOJSON: geojson path built')
        destcrs = QgsCoordinateReferenceSystem("EPSG:4326")
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GeoJSON"
        options.fileEncoding = "utf-8"
        context = QgsProject.instance().transformContext()
        options.ct = QgsCoordinateTransform(layer.sourceCrs() ,destcrs,context)
        if layer.selectedFeatureCount()>0:
            options.onlySelectedFeatures = True
            logging.debug('V2GEOJSON: about to write (selected feat only)')
            # TODO use .writeAsVectorFormatV3
            error = QgsVectorFileWriter.writeAsVectorFormatV3(layer=layer,fileName=geojson_path, transformContext=context,options=options)
            # error = QgsVectorFileWriter.writeAsVectorFormatV2(layer=layer,fileName=geojson_path, transformContext=context,options=options)
            # error = QgsVectorFileWriter.writeAsVectorFormat(layer,geojson_path , "utf-8", destcrs, "GeoJSON",onlySelected=True)
            logging.debug('V2GEOJSON: json written')
        else:
            logging.debug('V2GEOJSON: about to write')
            error = QgsVectorFileWriter.writeAsVectorFormatV3(layer=layer,fileName=geojson_path, transformContext=context,options=options)
            # error = QgsVectorFileWriter.writeAsVectorFormatV2(layer=layer,fileName=geojson_path, transformContext=context,options=options)
            #error = QgsVectorFileWriter.writeAsVectorFormat(layer,geojson_path , "utf-8", destcrs, "GeoJSON")
            logging.debug('V2GEOJSON: json written')

        assert error[0] == 0, 'error not equal to 0'
        assert error[0] == QgsVectorFileWriter.NoError, 'error not equal to NoError'
        # TODO get feedback working within report class
        # self.fb.pushInfo(f"export json --> {geojson_path}")
        logging.debug('V2GEOJSON: assert passed, about to load json')
        geojson = self.load_geojson(geojson_path)
        logging.debug('V2GEOJSON: json loaded')
        return geojson

    def load_geojson(self,file):
        ''' loads a json file to string '''
        with open(file) as f:
            data = json.load(f)
        return json.dumps(data)

    def add_failed(self, layer_title, subgroup, group, comment=None):
        ''' add a failed interest to the report'''
        logging.debug(f"REPORT add failed layer: {layer_title}")
        failedLyr = {'name':layer_title,
            'group':group,
            'subgroup':subgroup,
            'comment':comment}   

        self.failedLyrs.append(failedLyr)
        logging.debug('Interest appended to failed layers')

    def report(self,outfile):
        """ Build html report based on self.interests --> html file
        """
        #build summary
        reportDate = datetime.datetime.utcnow().strftime('%B %d %Y - %H:%M:%S') + ' UTC'
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(
            searchpath=os.path.join(self.template_path,self.TEMPLATE_RELATIVE_PATH))
            )
        template = env.get_template('home.html', parent='layout.html')
        intersecting_layers = []
        non_intersecting_layers=[]
        for i in self.interests:
            if ('value' in i.keys()):
                intersecting_layers.append(i)
            else:
                non_intersecting_layers.append(i)
        layers = [i for i in self.interests]
        layer_sort = sorted(intersecting_layers, key=lambda k: k['value'],reverse=True) 
        layers = layer_sort + non_intersecting_layers
        ahtml = template.render(aoi = self.aoi,interests=layers, reportDate=reportDate, failedLyrs = self.failedLyrs)
        #ahtml = template.render(species=aoi.species, shape=aoi.poly,aoi=aoi)
        outpath = os.path.dirname(outfile)
        # Check whether the specified path exists or not
        pathExist = os.path.exists(outpath)
        logging.debug(f'Output path {outpath} exists: {pathExist}')
        if not pathExist:      
            # Create a new directory because it does not exist 
            os.makedirs(outpath)
            logging.debug('Outpath created')
        with open(outfile, 'w') as f:
            f.write(ahtml)    
        logging.debug(f'Report written to file ({(os.path.getsize(outfile)/1000):.0f} KB)')
        #the last hurah!
        # arcpy.SetParameterAsText(1, outfile)
        env = None
        template = None
        return outfile

class oracle_pyqgis:
    ''' oracle_pyqgis has utilities for creating qgsVectorLayer objects for loading into QGIS
    constructor (database: str,
            host: str,
            user: str,
            port: int,
            password: str)
    '''
    # import ptvsd
    # ptvsd.debug_this_thread()

    def __init__(self,database,host,port,user,password):
        
        self.user_name = user
        self.user_pass = password
        self.host = host
        self.database = database
        self.port = port
        self.db = None
        self.open_db_connection()
    def __del__(self):
        # close db before destruction
        self.close_db_connection()
        self.db = None
        qdb = None

    def open_db_connection(self):
        ''' open_db_connection creates and opens a db connection to the oracle database
        '''
        logging.debug('Attempting db connection')
        driver ="QOCISPATIAL"
        conn_name = "bcgw_conn"
        qdb = QSqlDatabase()
        self.db = qdb.addDatabase(driver,conn_name)
        self.db.setDatabaseName(self.host + "/" + self.database)
        self.db.setUserName(self.user_name) 
        self.db.setPassword(self.user_pass) 
        db_open = self.db.open()
        logging.debug(f'db connection status: {db_open}')
        return db_open
    def close_db_connection(self):
        ''' close_db_connection closes db connection to the oracle database
        '''
        if self.db.isOpen():
            self.db.close()
            logging.debug(f'db connection closed')
                
    def create_layer_anyinteract(self,overlay_layer,layer_name,db_table,sql):
        ''' creates a qgsvectorlayer using an anyinteract query
            overlay_layer: qgsvectorlayer, QgsFeature
            layer_name: str,
            db_table: str
            usage = oracle_pyqgis.create_oracle_layer(self,overlay_layer=myQgsVectorLayer layer_name="My Layer", db_table="myschema.mytable")

        '''
        start_time = time.time()
        
        if isinstance(overlay_layer,QgsVectorLayer):
            rectangle = overlay_layer.extent()
        elif isinstance(overlay_layer,QgsFeature):
            rectangle = overlay_layer.geometry().boundingBox()
        else:
            # print ("unexpected overlay_layer type")
            raise TypeError('unexpected overlay_layer type')
        rect = [rectangle.xMinimum(), rectangle.yMinimum(), rectangle.xMaximum(), rectangle.yMaximum()]
        exnt_str = "{},{},{},{}".format(rect[0], rect[1], rect[2], rect[3])
        if sql is not None:
            if len(sql.strip())>0:
                sql = sql + " AND "
        else:
            sql = ''
        # print("start--- %s seconds ---" % (time.time() - start_time))
        geom_c = self.get_bcgw_geomcolumn(db_table=db_table)
        # print("query geom column--- %s seconds ---" % (time.time() - start_time))
        geom_type = self.get_bcgw_table_geomtype(db_table=db_table,geom_column_name=geom_c)
        # print("query geom type--- %s seconds ---" % (time.time() - start_time))
        key = self.get_bcgw_column_key(db_table=db_table)
        # print("query column key--- %s seconds ---" % (time.time() - start_time))
        query = f"(select * from {db_table} where {sql} sdo_ANYINTERACT ({geom_c}, SDO_GEOMETRY(2003, 3005, NULL,SDO_ELEM_INFO_ARRAY(1,1003,3),SDO_ORDINATE_ARRAY({exnt_str}))) = 'TRUE')"
        #con_str=f"dbname=\'{self.database}\' host={self.host} port={self.port} estimatedmetadata=true srid=3005 type={geom_type} table={query}"
        uri = QgsDataSourceUri()
        uri.setConnection(self.host, self.port, self.database, self.user_name, self.user_pass)
        uri.setDriver('oracle')
        uri.setSrid('3005')
        uri.setUseEstimatedMetadata(True)
        uri.setWkbType(geom_type)
        uri.setDataSource( "", query, geom_c, "", key)
        lyr = QgsVectorLayer(uri.uri(),layer_name,'oracle')
        if not lyr.isValid():
            print ('yikes')
        return lyr
    def create_oracle_layer(self,layer_name,db_table,sql=None):
        ''' create_oracle_layer creates and returns qgsVectorLayer
            layer_name: str,
            db_table: str
            usage = oracle_pyqgis.create_oracle_layer(self, layer_name="My Layer", db_table="myschema.mytable")
        '''
        # create an QgsVector from oracle table
        uri = QgsDataSourceUri()
        uri.setConnection(self.host, str(self.port),self.database, self.user_name, self.user_pass)
        schema, table = db_table.split('.')
        geom_c = self.get_bcgw_geomcolumn(db_table=db_table)
        geom_type = self.get_bcgw_table_geomtype(db_table=db_table,geom_column_name=geom_c)
        key = self.get_bcgw_column_key(db_table=db_table)
        if sql is not None and sql != '':
            # print (f"SQL: {sql}")
            uri.setDataSource(schema,table,aGeometryColumn=geom_c,aSql=sql,aKeyColumn=key)
        else:
            uri.setDataSource(schema, table, aGeometryColumn=geom_c,aKeyColumn=key)
        uri.setSrid('EPSG:3005')
        uri.setUseEstimatedMetadata(True)
        uri.setKeyColumn(key)
        uri.setWkbType(geom_type)
        tlayer = QgsVectorLayer(uri.uri(), layer_name, 'oracle')
        assert tlayer.isValid()
        tlayer.setCrs(QgsCoordinateReferenceSystem("EPSG:3005"))
        
        return tlayer
    def has_table(self,db_table):
        ''' has_table returns true if db_table exists for current user privilege
        '''
        owner, table = db_table.split('.')
        
        if not self.db.isOpen():
            try:
                if self.db.open() is False:
                    self.open_db_connection()
                assert self.db.isOpen()
            except:
                raise Exception(f"Failed to connect to {self.database}/{self.host}")
        q = QSqlQuery(self.db) 
        query = f"select VIEW_NAME NAME from all_views where owner = '{owner}' and VIEW_NAME = '{table}' union select TABLE_NAME NAME from all_tables where owner = '{owner}' and TABLE_NAME = '{table}'"
        q.exec(query)
        if q.first():
            return True
        else:
            return False
    def has_spatial_rows(self,db_table):
        ''' has_spatial_rows returns True if oracle table has rows with geometry
            usage:
            has_spatial_rows(WHSE_BASEMAPPING.BCGS_20K_GRID)
        '''
        owner,table = db_table.split('.') 
        geom_column_name = self.get_bcgw_geomcolumn(db_table=db_table)
        if not self.db.isOpen():
            try:
                if self.db.open() is False:
                    self.open_db_connection()
                assert self.db.isOpen()
            except:
                raise Exception(f"Failed to connect to {self.database}/{self.host}")
        q = QSqlQuery(self.db)
        # confrm there are rows
        query = f"SELECT rownum from {owner}.{table} t where rownum=1"
        q.exec(query)
        q.first()
        if q.value(0) is not None:
            query = f"SELECT MAX(t.{geom_column_name}.GET_GTYPE()) AS geometry_type from {owner}.{table} t where rownum <10"
            q.exec(query) 
            q.first()
        type_num = q.value(0)
        if type_num is not None:
            return True
        else:
            return False

    def get_bcgw_table_geomtype(self,db_table,geom_column_name):
        # get geometry type from oracle table - oracle stores multiple types so
        # this returns the maximum type ie multiline, multipolygon, multipoint if
        # present in geometry

        # type lookup dictionary {oracle_type_number:QgsWkbTypes}
        
        type_lookup =  {1:QgsWkbTypes.Point,
                        2:QgsWkbTypes.LineString,
                        3:QgsWkbTypes.Polygon,
                        5:QgsWkbTypes.MultiPoint,
                        6:QgsWkbTypes.MultiLineString,
                        7:QgsWkbTypes.MultiPolygon}
        
        owner,table = db_table.split('.') 
        if not self.db.isOpen():
            try:
                if self.db.open() is False:
                    self.open_db_connection()
                assert self.db.isOpen()
            except:
                raise Exception(f"Failed to connect to {self.database}/{self.host}")
        q = QSqlQuery(self.db) 
        query = f"SELECT MAX(t.{geom_column_name}.GET_GTYPE()) AS geometry_type from {owner}.{table} t where rownum <10"
        q.exec(query) 
        q.first()
        type_num = q.value(0)
        if type_num in type_lookup.keys():
            return type_lookup[type_num]
        else:
            raise TypeError(f"Unexpected SDO_GEOMETRY TYPE ({type_num}) from Table ({db_table})({geom_column_name})")

    def get_bcgw_geomcolumn(self,db_table):
        '''returns the name of the geometry column for oracle table '''
        owner,table = db_table.split('.') 
        if not self.db.isOpen():
            try:
                if self.db.open() is False:
                    self.open_db_connection()
                assert self.db.isOpen()
            except:
                raise Exception(f"Failed to connect to {self.database}/{self.host}")
        q = QSqlQuery(self.db) 
        query ="SELECT COLUMN_NAME from all_tab_columns where OWNER = '{}' AND TABLE_NAME = '{}' AND DATA_TYPE = 'SDO_GEOMETRY'".format(owner,table)  
        q.exec(query) 
        q.first() 
        geom_c = q.value(0)
        return geom_c

    def get_bcgw_column_key(self,db_table):
        ''' estimate a unique id column for an oracle table if OBJECTID does not exist '''
        # estimate a unique id column for an oracle table if OBJECTID does not exist
        owner,table = db_table.split('.') 
        if not self.db.isOpen():
            try:
                if self.db.open() is False:
                    self.open_db_connection()
                assert self.db.isOpen()
            except:
                raise Exception(f"Failed to connect to {self.database}/{self.host}")
        q = QSqlQuery(self.db)
        sql = f"SELECT cols.column_name \
        FROM all_tab_cols cols where cols.table_name = '{table}' and cols.COLUMN_NAME like \'OBJECTID\'"
        q.exec(sql)
        if q.first():
            key_c = q.value(0)
        else:
            sql = f"SELECT COLUMN_NAME FROM all_tab_cols where table_name = '{table}' \
                order by COLUMN_ID FETCH FIRST 1 ROWS ONLY"
            q.exec(sql)
            if q.first():
                key_c = q.value(0)

        return key_c
