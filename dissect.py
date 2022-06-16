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

from cgitb import reset
import sys
import os
import traceback

import jinja2
import json
import datetime
from osgeo import (gdal,
                ogr,
                osr)

from qgis.PyQt.QtCore import QCoreApplication,pyqtSignal
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
                       QgsWkbTypes,
                       QgsCoordinateReferenceSystem,
                       QgsCoordinateTransform,
                       QgsCoordinateTransformContext,
                       QgsApplication,
                       QgsFeature,
                       QgsVectorLayer,
                       QgsRasterLayer,
                       QgsVectorFileWriter,
                       QgsDataSourceUri,
                       QgsProject,
                       QgsMessageLog,
                       QgsTask,
                       Qgis
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
from functools import partial

# dev only
import logging

MESSAGE_CATEGORY = 'Messages'

def enable_remote_debugging():
    try:
        import ptvsd
        if ptvsd.is_attached():
            QgsMessageLog.logMessage("Remote Debug for Visual Studio is already active", MESSAGE_CATEGORY, Qgis.Info)
            logging.debug('Remote Debug for Visual Studio already attached')
            return
        ptvsd.enable_attach(address=('localhost', 5678), log_dir=os.path.join(self.CONFIG_PATH, '/ptvsd_log'))
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

    #INPUT = 'INPUT'
    AOI = 'AOI'
    XLS_CONFIG_IN = 'XLS_CONFIG_IN'
    DATABASE = 'DATABASE'
    USER = 'USER'
    PASSWORD = 'PASSWORD'
    OUTPUT = 'OUTPUT'
          
    def config(self):
        self.CONFIG_PATH = os.environ['QENV_CONFIG_PATH']
        if not os.path.exists(os.path.join(self.CONFIG_PATH, 'logs')):
            os.mkdir(os.path.join(self.CONFIG_PATH, 'logs'))

        logging.basicConfig(
        filename = os.path.join(self.CONFIG_PATH, 'logs', 'dissect.log'),
        # filemode = 'w',
        encoding='utf-8',
        level=logging.DEBUG,
        format = '%(name)s - %(levelname)s - %(message)s'
        )
        
        logging.debug('Run started at ' + datetime.datetime.now().strftime("%d%m%Y-%H-%M-%S"))

        try:
            enable_remote_debugging()
        except: 
            QgsMessageLog.logMessage("Debug for VS not enabled", MESSAGE_CATEGORY, Qgis.Critical)
            

        self.SECURE_TABLES_CONFIG = os.path.join(self.CONFIG_PATH,"protected.yml")
        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&ThabReport')
        self.protected_tables = self.get_protected_tables(self.SECURE_TABLES_CONFIG)
               
        # TODO add checkbox for 'add interests to map'
        self.add_interests = True
        self.tool_map_layers = []
        self.failed_layers =[]
        self.taskManager = QgsApplication.taskManager()
        self.tasks = []
        self.complete_tasks =[]
        self.report = None
        self.html_file = None
        
        
    def get_protected_tables(self,config_file):
        ''' Returns list of protected tables
        '''
        logging.debug(f"Loading protected tables yml: {config_file}")
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
        # TODO add param for useSelected checkbox
        if 'QENV_DB_USER' not in os.environ:
            user = ''
        else:
            user = os.environ['QENV_DB_USER']
        
        if 'QENV_DB' not in os.environ:
            db = ''
        else:
            db = os.environ['QENV_DB']
        if 'QENV_XLS_CONFIG' not in os.environ:
            xls_config = ''
        else:
            xls_config = os.environ['QENV_XLS_CONFIG']
        if 'QENV_DB_PASS' not in os.environ:
            dbpass = ''
        else:
            dbpass = os.environ['QENV_DB_PASS']
        if 'QENV_OUT' not in os.environ:
            outfile = ''
        else:
            outfile = os.environ['QENV_OUT']+datetime.datetime.now().strftime("%d%m%Y-%H-%M-%S")+".html"
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.AOI,
                self.tr('Area of Interest'),
                [QgsProcessing.TypeVectorPolygon]
            )

        )
        self.addParameter(
            QgsProcessingParameterFile(
                name = self.XLS_CONFIG_IN,
                description = self.tr('Input .xlsx coniguration file'),
                optional = False,
                extension = "xlsx",
                defaultValue = xls_config
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.DATABASE,
                self.tr('Database'),
                defaultValue = db
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.USER,
                self.tr('DB Username'),
                defaultValue = user
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.PASSWORD,
                self.tr('DB Password'),
                defaultValue = dbpass
            )
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.OUTPUT,
                self.tr('Output File eg. T:/myproject/myproject_overlap_report.html'),
                'HTML files (*.html)',
                defaultValue = outfile
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
        aoi = self.parameterAsVectorLayer(parameters, 'AOI', context)
        config_xls = self.parameterAsFile(parameters, 'XLS_CONFIG_IN', context)
        user = self.parameterAsString(parameters, 'USER', context)
        password = self.parameterAsString(parameters, 'PASSWORD', context)
        output_html = self.parameterAsFileOutput(parameters, 'OUTPUT', context)
        database = self.parameterAsString(parameters, 'DATABASE', context)
        # do these manually for now (not in dialogue)
        host = 'bcgw.bcgov'  
        port = '1521'
               
        if feedback.isCanceled():
            feedback.pushInfo('Process cancelled by user.')
            return {}

        # TODO configure progress bar for processing 
        # see ln 187 in __init__.py for qgis_plugin for old code for message bar

        aoi_in = aoi
        xls_file = config_xls
        self.html_file = output_html


        # TODO set up use selected feature
        use_selected = False

        try:
            if aoi_in.selectedFeatureCount()>0 and use_selected == True:
                #export to in memory layer
                aoi = processing.run("native:saveselectedfeatures", {'INPUT': aoi_in, 'OUTPUT': 'memory:'})['OUTPUT']
            else:
                aoi = aoi_in.clone()
            if aoi.sourceCrs().isGeographic:
                parameter = {'INPUT': aoi, 'TARGET_CRS': 'EPSG:3005','OUTPUT': 'memory:aoi'}
                aoi = processing.run('native:reprojectlayer', parameter)['OUTPUT']
            QgsProject.instance().addMapLayer(aoi,False)
            # TODO: remove addMapLayer above?
            # create db object 
            oq_helper = oracle_pyqgis(database=database,host=host,port=port,user=user,password=password)

            # init report with AOI
            self.report = report(aoi,template_path=self.CONFIG_PATH,feedback=None)

            # connect trigger to method to run once all geoprocessing is done
            # QgsApplication.taskManager().allTasksFinished.connect(self.generate_report)
            # creates list of all fc to compare aoi too
            parsed_input = self.parse_config(xls_file)
            logging.debug('Config xlsx parsed successfully')

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
                if feedback.isCanceled():
                    feedback.pushInfo('Process cancelled by user.')
                    return {}
                for key in tab_dict:
                    if feedback.isCanceled():
                        feedback.pushInfo('Process cancelled by user.')
                        return {}
                    tab = tab_dict[key]
                    for dic in tab:
                        # iterate over data definitions
                        if feedback.isCanceled():
                            feedback.pushInfo('Process cancelled by user.')
                            return {}
                        lyr_start = time.time()
                        layer_title = dic['Layer Name']
                        if layer_title is not None:
                            layer_title = layer_title.strip()
                            logging.debug(f'Processing {layer_title}')
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
                            if (layer_expansion is None):
                                layer_expansion = ''
                            if len(layer_expansion)>0:
                                summary_fields = [f.strip() for f in layer_expansion.split(',')]
                            else:
                                summary_fields = []
                            #QgsMessageLog.logMessage(layer_title,self.PLUGIN_NAME,Qgis.Info)
                            feedback.pushInfo('--- ' + str(layer_title) + ' ---')
                            features = aoi.getFeatures()
                            logging.debug(f'Starting task for {layer_title}')
                            task = clipVectorTask(aoi,key,location,layer_subgroup,layer_title,layer_sql,summary_fields,feedback,oq_helper,layer_table)
                            # task.run() # only do this if you want to bypass taskManager
                            self.tasks.append(task)
                        else:
                            logging.error(f'----- No Title {layer_title}')
        except:
            logging.error(f'Error in processAlgorithm')


        logging.debug(f'Loading {len(self.tasks)} tasks to .taskManager')
        # allow for existing tasks in taskManager. 
        loaded_task_ids = []
        for task in self.tasks:
            task.result.connect(lambda r: self.logTask(r))
            self.taskManager.addTask(task)
            loaded_task_ids.append(self.taskManager.taskId(task))
        logging.debug(f'All tasks loaded')    
        while len(loaded_task_ids) > 0:
            for id in loaded_task_ids:
                if id not in [self.taskManager.taskId(t) for t in self.taskManager.activeTasks()]:
                    loaded_task_ids.remove(id)
            QCoreApplication.processEvents()
        logging.debug("All tasks complete")
        logging.debug("Adding tasks to report")
        for task in self.complete_tasks:
            logging.debug(f"task {task['layer_title']}")
            if task['result'] is not None:
                if task['result'].featureCount()>0:
                    if self.add_interests is True:
                        QgsProject.instance().addMapLayer(task['result'])
                        self.tool_map_layers.append(task['result'].id())
                if task['layer_table'] not in self.protected_tables:
                    self.report.add_interest(task['result'],task['key'],task['layer_subgroup'],task['summary_fields'],secure=False)
                else:
                    self.report.add_interest(task['result'],task['key'],task['layer_subgroup'],task['summary_fields'],secure=True)
            else:
                logging.debug(f"task {task['layer_title']} did not generate output")
        result_msg = {}
        self.report.report(self.html_file)
        result_msg[self.OUTPUT] = self.html_file
        return result_msg 
    def logTask(self,task_results):
        self.complete_tasks.append(task_results)

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
            error = QgsVectorFileWriter.writeAsVectorFormatV3(layer=layer,fileName=geojson_path, transformContext=context,options=options)
            logging.debug('V2GEOJSON: json written')
        else:
            logging.debug('V2GEOJSON: about to write')
            error = QgsVectorFileWriter.writeAsVectorFormatV3(layer=layer,fileName=geojson_path, transformContext=context,options=options)
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
class  clipVectorTask(QgsTask):
    """ This is a QgsTask that creates and clips a file based vector layer 
    based on a file location"""
    result = pyqtSignal(dict)
    def __init__(self,clip_feature,key,location,layer_subgroup,layer_title,layer_sql,summary_fields,feedback,oracle_helper_obj=None,layer_table=None):
        super().__init__(layer_title,QgsTask.CanCancel)
        import ptvsd
        ptvsd.debug_this_thread()
        self.aoi = clip_feature
        self.location = location
        self.layer_title = layer_title
        self.layer_sql = layer_sql
        self.oq_helper = oracle_helper_obj
        self.layer_table = layer_table
        self.layer_subgroup = layer_subgroup
        self.summary_fields = summary_fields
        self.key = key
        self.output = None
        self.exception = None

    def run(self):
        """ run task
        """
        logging.debug(f'{self.layer_title} exists, starting processing')
        features = self.aoi.getFeatures()
        results = []
        result = None
        for item in features: # iterate through each item in aoi
            self.aoi.select(item.id())
            if self.location == 'BCGW':
                results.append(self.process_oracle())
            elif os.path.exists(self.location):
                results.append(self.process_file_vector())
            self.aoi.removeSelection()
        if len(results)>1:
            self.merge_results(results)
        elif len(results)==1:
            result = results[0]
        else:
            return False
    
        self.OUTPUT = result
        return True
    def process_file_vector(self):
        rlayer = None
        vlayer = None
        result = None
        filename, file_extension = os.path.splitext(self.location)
        if len(self.layer_sql)>0:
            location_sql = f"|subset={self.layer_sql}"
        else:
            location_sql = ""
        coverage = False
        if os.path.isdir(self.location):
            dir_files = os.listdir(self.location)
            for f in dir_files:
                if ".adf" in f:
                    coverage = True
                    break
        if coverage is True:
            # load coverage
            for f in os.listdir(self.location):
                if f in ['arc.adf','pal.adf','lab.adf','cnt.adf']:
                    vlayer = QgsVectorLayer(os.path.join(self.location,f), self.layer_title, "ogr")
                if f == 'hdr.adf':
                    rlayer = QgsRasterLayer(os.path.join(self.location,f),self.layer_title)
        elif file_extension in ['.shp','.kml','.kmz','.geojson']:
            file_location = self.location + location_sql
            vlayer = QgsVectorLayer(file_location, self.layer_title, "ogr")
            assert vlayer.isValid(),f"Failed to add {self.layer_title}:{filename}"
        elif file_extension in ['.tif']:
            rlayer = QgsRasterLayer(self.location,self.layer_title)
            assert rlayer.isValid(),f"Failed to add {self.layer_title}:{filename}"
        elif file_extension in ['.gdb','gpkg']:
            ogr_string = f"{self.location}|layername={self.layer_table}{location_sql}"
            vlayer = QgsVectorLayer(ogr_string, self.layer_title, "ogr")
        else:
            vlayer = None
        if vlayer is not None:
            logging.debug(f'{self.layer_title} is vector layer, starting processing')
            try:
                if vlayer.isValid():
                    vlayer.setSubsetString(self.layer_sql)
                    if vlayer.featureCount()>0:
                        logging.debug(f'{self.layer_title} has valid geometry')
                        result = processing.run("native:clip", {'INPUT':vlayer, 
                            'OVERLAY': QgsProcessingFeatureSourceDefinition(self.aoi.id(), True), 'OUTPUT':f'memory:{self.layer_title}'})['OUTPUT']
                        logging.debug(f'{self.layer_title} clipped')
                    else:
                        logging.debug(f'{self.layer_title} created empty vector layer')
            except:
                vlayer.setSubsetString(self.layer_sql)
                if vlayer.featureCount()>0:
                    logging.debug(f'{self.layer_title} has invalid geometry, fixing...')
                    f_layer = processing.run("native:fixgeometries", {'INPUT':vlayer,'OUTPUT':'memory:{layer_title}fix'})['OUTPUT']
                    logging.debug(f'{self.layer_title} geo fixed')
                    result = processing.run("native:clip", {'INPUT':f_layer, 
                        'OVERLAY': QgsProcessingFeatureSourceDefinition(self.aoi.id(), True), 'OUTPUT':f'memory:{self.layer_title}'})['OUTPUT']
                    logging.debug(f'{self.layer_title} clipped')
        return result

    def process_oracle(self):
        # get overlapping features
        has_table = self.oq_helper.has_table(self.layer_table)
        if has_table == True:
            has_spatial_rows = self.oq_helper.has_spatial_rows(self.layer_table)
        else:
            has_spatial_rows = False
        if has_table == True and has_spatial_rows == True:
            # get features from bbox
            selected_features = self.oq_helper.create_layer_anyinteract(overlay_layer=self.aoi,layer_name=self.layer_title,db_table=self.layer_table,sql=self.layer_sql)
            try:
                if selected_features.featureCount()>0:
                    # clip them
                    result = processing.run("native:clip", {'INPUT':selected_features, 'OVERLAY': QgsProcessingFeatureSourceDefinition(self.aoi.id(), True), 'OUTPUT':f'memory:{self.layer_title}'})['OUTPUT']
                    logging.debug(f"Clip of {self.layer_title} has {result.featureCount()} features")
                else:
                    # return layer with no features
                    logging.debug(f'Oracle {self.layer_title} has no feature in AOI')
                    result = selected_features
            except:
                try:
                    logging.debug(f"Clip of {self.layer_title} failed attempt to repair geometry")
                    f_layer = processing.run("native:fixgeometries", {'INPUT':selected_features,'OUTPUT':'memory:{layer_title}'})['OUTPUT']
                    result = processing.run("native:clip", {'INPUT':f_layer, 'OVERLAY': QgsProcessingFeatureSourceDefinition(self.aoi.id(), True), 'OUTPUT':f'memory:{self.layer_title}'})['OUTPUT']
                    logging.debug(f"Clip of fixed {self.layer_title} has {result.featureCount()} features")
                    
                except:
                    logging.debug(f"Error in accessing {self.layer_title}")
        return result

    def merge_results(self,vector_layers):
        try:
            if len(vector_layers)>1:
                result = processing.run("native:mergevectorlayers", 
                    {'LAYERS':vector_layers, 'CRS':QgsCoordinateReferenceSystem('EPSG:3005'),'OUTPUT':f'memory:{self.layer_title}'})['OUTPUT']
                result.setCrs(QgsCoordinateReferenceSystem('EPSG:3005'),True)
            else:
                result = vector_layers[0]
            if result.crs().authid() != 'EPSG:3005':
                result = processing.run('native:reprojectlayer', 
                    {'INPUT': result, 'TARGET_CRS': 'EPSG:3005', 'OUTPUT': f'memory:{self.layer_title}'})['OUTPUT']
            idx = result.fields().indexFromName( 'SE_ANNO_CAD_DATA' )
            if idx != (-1):
                res = result.dataProvider().deleteAttributes([idx])
                result.updateFields()
        except:
            self.feedback.pushInfo(f"Could not merge results for {self.layer_title}")
        return result
        
    def finished(self,result):
        if result:
            QgsMessageLog.logMessage(
                f'Clip file vectorlayer {self.description()} completed',
                MESSAGE_CATEGORY, Qgis.Success)
            # self.location = location
            # self.layer_title = layer_title
            # self.layer_sql = layer_sql
            # self.oq_helper = oracle_helper_obj
            # self.layer_table = layer_table
            # self.layer_subgroup = layer_subgroup
            # self.summary_fields = summary_fields
            # self.key = key
            self.result.emit({"location":self.location,
                            "layer_title":self.layer_title,
                            "layer_sql":self.layer_sql,
                            "layer_table":self.layer_table,
                            "layer_subgroup":self.layer_subgroup,
                            "summary_fields":self.summary_fields,
                            "key":self.key,
                            "result":self.OUTPUT})
        else:
            QgsMessageLog.logMessage(
                    f'Clip file vectorlayer {self.description()} Exception: {self.exception}',
                    MESSAGE_CATEGORY, Qgis.Critical)
            raise self.exception # this can be populated in task with eg. self.exception = Exception("Layer failed to merge")
    def cancel(self):
        QgsMessageLog.logMessage(
            'Clip file vectorlayer {self.description} was cancelled',
            MESSAGE_CATEGORY, Qgis.Info)
        super().cancel()
