#-----------------------------------------------------------
# Copyright (C) 2015 Martin Dobias
#-----------------------------------------------------------
# Licensed under the terms of GNU GPL 2
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#---------------------------------------------------------------------
import sys
import os

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
                       Qgis
                       )

from qgis import processing
import pandas as pd
import tempfile
import time
import yaml
import re
from PyQt5.QtWidgets import QAction, QMessageBox, QProgressBar,QDockWidget,QTabWidget
from .thab_dialog import ThabReportDialog
from PyQt5.QtCore import *
from PyQt5.QtGui import *

#from .resources import *
def classFactory(iface):
    return ThabReport(iface)


class ThabReport:
    PLUGIN_NAME = 'QGIS Report'
    def __init__(self, iface):
        self.iface = iface
        config_path = r""
        
        self.SECURE_TABLES_CONFIG = os.path.join(config_path,"app.yml")
        self.DATABASE_CONFIG_FILE = os.path.join(config_path,"app.yml")
        self.DATABASE_CONFIG = yaml.safe_load(open(self.DATABASE_CONFIG_FILE,'r'))['database']
        self.APP_ROOT = yaml.safe_load(open(self.DATABASE_CONFIG_FILE,'r'))['application']['root']
        xls_file_name = yaml.safe_load(open(self.DATABASE_CONFIG_FILE,'r'))['data']
        self.XLS_CONFIG = os.path.join(config_path,xls_file_name)
        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&ThabReport')
        self.protected_tables = self.get_protected_tables(self.SECURE_TABLES_CONFIG)
        
        
        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None
        self.add_interests = False
        self.tool_map_layers = []
        self.failed_layers =[]
        self.dlg = ThabReportDialog()

    def initGui(self):
        
        self.action = QAction(self.PLUGIN_NAME, self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.action)
        # self.add_action(icon_path=None,
        #                 text='Go!',
        #                 callback=self.run,
        #                 parent=self.iface.mainWindow)
        self.first_start = True
    def unload(self):
        self.iface.removeToolBarIcon(self.action)
        del self.action

    def run(self):
        
        if self.first_start == True:
            self.first_start = False
            self.dlg = ThabReportDialog()
            self.dlg.layer_selection_trigger()
        
        self.dlg.show()
        result = self.dlg.exec_()
        if self.dlg.useSelected.checkState() == 2:
            use_selected = True
        else:
            use_selected = False
        if result:
            user = self.dlg.username_input.text()
            password = self.dlg.password_input.text()
            aoi = self.dlg.vector_input.currentLayer()
            self.add_interests = self.dlg.addInterests.isChecked()
            assert isinstance(aoi, QgsVectorLayer)
            report_result = self.processAlgorithm(aoi=aoi,
                                    user=user,
                                    password=password,
                                    config_xls= self.XLS_CONFIG,#self.dlg.xls_input.filePath(),
                                    output_html=self.dlg.report_output.filePath(),
                                    use_selected=use_selected)
            donemsg = QMessageBox()
            if len(self.failed_layers)>0:
                layer_str = '\n'.join(self.failed_layers)
                donemsg.setText(f"Your report is complete but some layers could not be validated:" + '\n\n' + layer_str)
            else:
                donemsg.setText("Your report is complete")
            donemsg.setInformativeText(f"{self.dlg.report_output.filePath()}")
            donemsg.setStandardButtons(QMessageBox.Ok)
            donemsg_rslt = donemsg.exec_()
            QgsMessageLog.logMessage("Completed!",self.PLUGIN_NAME,Qgis.Info)
            

    def tr(self, message):
        """Get the translation for a string using Qt translation API.
        We implement this ourselves since we do not inherit QObject.
        :param message: String for translation.
        :type message: str, QString
        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('ThabReport', message)

    def get_protected_tables(table,config_file):
        ''' Returns list of protected tables
        '''
        conf = yaml.safe_load(open(config_file,'r'))['protected_data']
        return conf['tables']

    def parse_config(self,xlsx):
        ''' parses xls into list of dictionaries 
            {'xls tab name':[{'Column1':'',
                            'Column2':'',
                            'Column3':'',
                            'Column4':''},{}]
        '''
        assert os.path.exists(xlsx)
        data = []
        xl = pd.ExcelFile(xlsx)
        assert len(xl.sheet_names)>0, f"Problem reading excel file ({xlsx})"
        for worksheet in xl.sheet_names:
            df = xl.parse(worksheet)
            df = df.where(pd.notnull(df), None)     
            d = df.to_dict('records')
            data.append({worksheet:d})
        return data

    def processAlgorithm(self,aoi,user,password,config_xls,output_html,use_selected=False):
        
        aoi_in =aoi
        
        database = self.DATABASE_CONFIG['database']
        host = self.DATABASE_CONFIG['host']
        port = str(self.DATABASE_CONFIG['port'])
        user = user
        password = password
        output = output_html
        xls_file = config_xls

        progress = QProgressBar()
        progress.setMaximum(100)
        progress.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        progressMessageBar = self.iface.messageBar().createMessage("If software appears frozen, do not touch -tool is still working!              Progress Status:")
        progressMessageBar.layout().addWidget(progress)
        self.iface.messageBar().pushWidget(progressMessageBar, level=0)
        self.iface.mainWindow().blockSignals(True) #turns off CRS dialog box when creating 
        QgsMessageLog.logMessage(f"Starting {self.PLUGIN_NAME}",self.PLUGIN_NAME,Qgis.Info)
        progress.setValue(1)
        
        try:
            if aoi_in.selectedFeatureCount()>0 and use_selected == True:
                #export to in memory layer
                aoi = processing.run("native:saveselectedfeatures", {'INPUT': aoi_in, 'OUTPUT': 'memory:'})['OUTPUT']
            else:
                if aoi_in.featureCount()>20:
                    msg = QMessageBox()
                    msg.setText(f"Your area of interest ({aoi_in.name()}) contains many features")
                    msg.setInformativeText("would you like to push the limits?")
                    msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
                    msg_rslt = msg.exec_()
                    if not msg_rslt == QMessageBox.Ok:
                        QgsMessageLog.logMessage("User initiated exit",self.PLUGIN_NAME,Qgis.Critical)
                        return False
                aoi = aoi_in.clone()
            if aoi.sourceCrs().isGeographic:
                parameter = {'INPUT': aoi, 'TARGET_CRS': 'EPSG:3005','OUTPUT': 'memory:aoi'}
                aoi = processing.run('native:reprojectlayer', parameter)['OUTPUT']
            QgsProject.instance().addMapLayer(aoi,False)
            if aoi.wkbType() == QgsWkbTypes.Point:
                raise TypeError('Area of Interest cannot be a point geometry')
            if aoi.wkbType() == QgsWkbTypes.LineString:
                raise TypeError('Area of Interest cannot be a line geometry')                
            # set tab in messageLog
            dock = self.iface.mainWindow().findChild(QDockWidget, 'MessageLog')
            tabs = dock.findChild(QTabWidget, 'tabWidget')
            for tab in range(tabs.count()):
                text = tabs.tabText(tab)
                if text == self.PLUGIN_NAME:
                    tabs.setCurrentIndex(tab)
                    break

            #create object 
            oq_helper = oracle_pyqgis(database=database,host=host,port=port,user=user,password=password)
            
            # init report with AOI
            report_obj = report(aoi,self.APP_ROOT,feedback=None)

            # creates list of all fc to compare aoi too
            parsed_input = self.parse_config(xls_file)
            progress.setValue(5)
            
            #estimate the number of layers to process
            estimated_count = 0
            for t in parsed_input:
                for k in t:
                    for d in t[k]:
                        if d['Layer Name'] is not None:
                            estimated_count += 1
            i = (90 / estimated_count)           
            #feedback.pushInfo(f"Evaluating {estimated_count} interests")
            for tab_dict in parsed_input:
                for key in tab_dict:
                    tab = tab_dict[key]
                    for dic in tab:
                        lyr_start = time.time()
                        layer_title = dic['Layer Name']
                        if layer_title is not None:
                            layer_title = layer_title.strip()
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
                            feature_layer_lst = [] #build empty layer list for each obj to be merged at end of unique feature cycle
                            QgsMessageLog.logMessage(layer_title,self.PLUGIN_NAME,Qgis.Info)
                            features = aoi.getFeatures()
                            for item in features: #iterate through each item in aoi
                                aoi.select(item.id())
                                if (location == 'BCGW'):
                                    assert layer_table is not None
                                    # get overlapping features
                                    has_table = oq_helper.has_table(layer_table)
                                    if has_table == True:
                                        has_spatial_rows = oq_helper.has_spatial_rows(layer_table)
                                    else:
                                        has_spatial_rows = False
                                    if has_table == True and has_spatial_rows == True:
                                        # get features from bbox
                                        selected_features = oq_helper.create_layer_anyinteract(overlay_layer=aoi,layer_name=layer_title,db_table=layer_table,sql=layer_sql)
                                        try:
                                            if selected_features.featureCount()>0:
                                                # clip them
                                                result = processing.run("native:clip", {'INPUT':selected_features, 'OVERLAY': QgsProcessingFeatureSourceDefinition(aoi.id(), True), 'OUTPUT':f'memory:{layer_title}'})['OUTPUT']
                                                if result.featureCount()>0:
                                                    QgsMessageLog.logMessage(f"{layer_title} with ({result.featureCount()}) overlapping features",self.PLUGIN_NAME,Qgis.Info)
                                            else:
                                                # return layer with no features
                                                result = selected_features
                                        except:
                                            try:
                                                f_layer = processing.run("native:fixgeometries", {'INPUT':selected_features,'OUTPUT':'memory:{layer_title}'})['OUTPUT']
                                                result = processing.run("native:clip", {'INPUT':f_layer, 'OVERLAY': QgsProcessingFeatureSourceDefinition(aoi.id(), True), 'OUTPUT':f'memory:{layer_title}'})['OUTPUT']
                                                
                                            except:
                                                QgsMessageLog.logMessage(f"Error in accessing {layer_title}",self.PLUGIN_NAME,Qgis.Warning)
                                        if result is not None:
                                            # feedback.pushInfo(f"result type {type(result)}")
                                            # feedback.pushInfo(f"clip result count: {result.featureCount()}")
                                            feature_layer_lst.append(result)
                                    else:
                                        if has_table:
                                            QgsMessageLog.logMessage(f"No data in table: BCGW {layer_table}",self.PLUGIN_NAME,Qgis.Warning)
                                        else:
                                            QgsMessageLog.logMessage(f"Can not access: BCGW {layer_table}",self.PLUGIN_NAME,Qgis.Warning)
                                elif (location is not None):
                                    if os.path.exists(location):
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
                                            QgsMessageLog.logMessage(f"No loading function for {layer_title}: {location}",self.PLUGIN_NAME,Qgis.Warning)
                                        if vlayer is not None:
                                            try:
                                                if vlayer.isValid():
                                                    vlayer.setSubsetString(layer_sql)
                                                    if vlayer.featureCount()>0:
                                                        result = processing.run("native:clip", {'INPUT':vlayer, 'OVERLAY': QgsProcessingFeatureSourceDefinition(aoi.id(), True), 'OUTPUT':f'memory:{layer_title}'})['OUTPUT']
                                                    else:
                                                        QgsMessageLog.logMessage(f"Definintion Query for {layer_title}: {location} | {layer_sql}",self.PLUGIN_NAME,Qgis.Warning)
                                                else:
                                                    QgsMessageLog.logMessage(f"Vector layer invalid {layer_title}: {location} | {layer_table}({location_sql})",self.PLUGIN_NAME,Qgis.Critical)
                                            except:
                                                vlayer.setSubsetString(layer_sql)
                                                if vlayer.featureCount()>0:
                                                    f_layer = processing.run("native:fixgeometries", {'INPUT':vlayer,'OUTPUT':'memory:{layer_title}fix'})['OUTPUT']
                                                    result = processing.run("native:clip", {'INPUT':f_layer, 'OVERLAY': QgsProcessingFeatureSourceDefinition(aoi.id(), True), 'OUTPUT':f'memory:{layer_title}'})['OUTPUT']
                                                else:
                                                    QgsMessageLog.logMessage(f"Definintion Query for {layer_title}: {location} | {layer_sql}",self.PLUGIN_NAME,Qgis.Warning)

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
                                        QgsMessageLog.logMessage(f"Can not make valid: {location}",self.PLUGIN_NAME,Qgis.Warning)
                                        self.failed_layers.append(layer_title)

                                aoi.removeSelection()
                            if len(feature_layer_lst) > 0:
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
                                    QgsMessageLog.logMessage(f"Could not merge results for {layer_title}",self.PLUGIN_NAME,Qgis.Critical)
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
                                QgsMessageLog.logMessage(f"{layer_title}: {delta_time} seconds",self.PLUGIN_NAME,Qgis.Info)
                                if result is not None:      
                                    if result.featureCount()>0:
                                        if self.add_interests is True:
                                            QgsProject.instance().addMapLayer(result)
                                            self.tool_map_layers.append(result.id())
                                    if layer_table not in self.protected_tables:
                                        report_obj.add_interest(result,key,layer_subgroup,summary_fields,secure=False)
                                    else:
                                        report_obj.add_interest(result,key,layer_subgroup,summary_fields,secure=True)
                                p = progress.value()
                                progress.setValue(p+i)
                            except:
                                 QgsMessageLog.logMessage(f"Failed to add interest {layer_title}",self.PLUGIN_NAME,Qgis.Warning,True)
            # write report
            result = report_obj.report(output)
            QgsProject.instance().removeMapLayer(aoi.id())
            

        except Exception as e:
            QgsProject.instance().removeMapLayer(aoi.id())
            for lyr_id in self.tool_map_layers:
                QgsProject.instance().removeMapLayer(lyr_id)
            raise QgsProcessingException(sys.exc_info())

        progress.setValue(100)
        self.iface.messageBar().clearWidgets()
        return {'OUTPUT': result}

    def gdal_polygonize(self,src_raster,raster_band=1,vector_value_field='DN'):
        ''' gdal_polygonize polygonizes the src_raster to temporary shape file
        '''
        sourceRaster = gdal.Open(src_raster)
        band = sourceRaster.GetRasterBand(raster_band)
        # bandArray = band.ReadAsArray()
        outShapefile = os.path.join(tempfile.gettempdir(),"polygonized.shp")
        driver = ogr.GetDriverByName("ESRI Shapefile")
        if os.path.exists(outShapefile):
            driver.DeleteDataSource(outShapefile)

        shp_srs = osr.SpatialReference()
        shp_srs.ImportFromWkt(sourceRaster.GetProjectionRef())

        outDatasource = driver.CreateDataSource(outShapefile)
        outLayer = outDatasource.CreateLayer("polygonized", srs=shp_srs)
        new_fld = ogr.FieldDefn('DN', ogr.OFTInteger)
        outLayer.CreateField(new_fld)
        gdal.Polygonize( band, None, outLayer, 0, [], callback=None )
        return outShapefile
    
    def gdal_raster_clip(self,in_raster,vector_mask):
        ''' gdal_raster_clip clips raster to vector mask
            vector mask must be .shp or QgsVectorLayer
        '''
        if isinstance(in_raster,QgsRasterLayer):
            rst = in_raster.dataProvider().dataSourceUri()
        else:
            rst = in_raster
        if isinstance(vector_mask,QgsVectorLayer):
            tmpshp = 'clip_shp.shp'
            clp_shp = self.vectorlayer_to_shp(vector_mask,tmpshp)
        else:
            clp_shp = vector_mask
        output_raster = os.path.join(os.environ['TEMP'],'tmp_clip_raster.tif')
        
        if os.path.exists(output_raster):
            os.remove(output_raster)

        ds = gdal.Warp(output_raster,rst,cutlineDSName=clp_shp,cropToCutline=True,warpOptions = [ 'CUTLINE_ALL_TOUCHED=TRUE' ])
        return output_raster

    def vectorlayer_to_shp(self,layer,out_name,folder='TEMP',only_selected=True):
        '''Export QgsVectorlayer to shapefile
            layer : QgsVectorLayer
            out_name: Str 
            folder: Str
            only_selected: Boolean
            
            example usage returns exported selected features as shapefile path "T:/test/layer.shp"
            my_shp = vectorlayer_to_shp(vlayer,"layer.shp","T:/test",True)
            
            "TEMP" folder saves file in os.environ["TEMP"] location
        '''

        file_name = out_name
        if folder=='TEMP':
            temp_path = os.environ['TEMP']
            tempfile = os.path.join(temp_path,file_name)
            if os.path.exists(tempfile):
                driver = ogr.GetDriverByName('ESRI Shapefile')
                driver.DeleteDataSource(temp_path)
        else:
            temp_path = folder
            assert os.path.exists(folder), f"Output folder does not exist: {folder}"
        
        path = os.path.join(temp_path,file_name)
        destcrs = layer.dataProvider().crs()#QgsCoordinateReferenceSystem("EPSG:4326")
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "ESRI Shapefile"
        options.fileEncoding = "utf-8"
        context = QgsProject.instance().transformContext()
        options.ct = QgsCoordinateTransform(layer.sourceCrs() ,destcrs,context)
        if layer.selectedFeatureCount()>0 and only_selected is True:
            options.onlySelectedFeatures = True
            error = QgsVectorFileWriter.writeAsVectorFormatV2(layer=layer,fileName=path, transformContext=context,options=options)
        else:
            error = QgsVectorFileWriter.writeAsVectorFormatV2(layer=layer,fileName=path, transformContext=context,options=options)        
        
        assert error[0] == QgsVectorFileWriter.NoError
        
        return path

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
    
    TEMPLATE_RELATIVE_PATH = 'templates'

    def __init__(self,aoi,template_path,feedback):
        self.fb = feedback
        assert os.path.exists(os.path.join(template_path,self.TEMPLATE_RELATIVE_PATH))
        self.interests = []
        self.aoi = self.aoi_info(aoi)
        self.aoi_layer = aoi
        
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
        # self.fb.pushInfo(f"REPORT add interest: {intersected_layer.name()}({intersected_layer.featureCount()})")
        interest = {'name':intersected_layer.name(),
            'group':group,
            'subgroup':subgroup}
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
                raise Exception (f"Unexpected geometry type:{geom_type}")
            value_merge = []
            for sf in summary_fields:
                assert sf in fieldNames, f"summary field ({sf}) does not exist in layer({intersected_layer.name()})"
                value_merge.append(str(f[sf]))
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
                interest['geojson'] = self.vectorlayer_to_geojson(intersected_layer)
        else:
            interest['geojson'] = None
            interest['field_summary'] = []
        self.interests.append(interest)
    def vectorlayer_to_geojson(self,layer):
        '''Export QgsVectorlayer to temp geojson'''
        file_name = layer.name().replace(' ','_').replace('.','_') + ".geojson"
        file_name = file_name.replace('/','_')
        file_name = file_name.replace('\\','_')
        temp_path = os.environ['TEMP']
        geojson_path = os.path.join(temp_path,file_name)
        destcrs = QgsCoordinateReferenceSystem("EPSG:4326")
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GeoJSON"
        options.fileEncoding = "utf-8"
        context = QgsProject.instance().transformContext()
        options.ct = QgsCoordinateTransform(layer.sourceCrs() ,destcrs,context)
        if layer.selectedFeatureCount()>0:
            options.onlySelectedFeatures = True
            error = QgsVectorFileWriter.writeAsVectorFormatV2(layer=layer,fileName=geojson_path, transformContext=context,options=options)
            #error = QgsVectorFileWriter.writeAsVectorFormat(layer,geojson_path , "utf-8", destcrs, "GeoJSON",onlySelected=True)
        else:
            error = QgsVectorFileWriter.writeAsVectorFormatV2(layer=layer,fileName=geojson_path, transformContext=context,options=options)
            #error = QgsVectorFileWriter.writeAsVectorFormat(layer,geojson_path , "utf-8", destcrs, "GeoJSON")
        
        assert error[0] == QgsVectorFileWriter.NoError
        # self.fb.pushInfo(f"export json --> {geojson_path}")
        geojson = self.load_geojson(geojson_path)
        return geojson

    
    def load_geojson(self,file):
        ''' loads a json file to string '''
        with open(file) as f:
            data = json.load(f)
        return json.dumps(data)
    def report(self,outfile):
        """ Build html report based on self.interests --> html file
        """
        #build summary
        reportDate = datetime.datetime.utcnow().strftime('%B %d %Y - %H:%M:%S') + ' UTC'
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(
            searchpath=os.path.join(self.PATH,self.TEMPLATE_RELATIVE_PATH))
            )
        template = env.get_template('home.html')
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
        ahtml = template.render(aoi = self.aoi,interests=layers, reportDate=reportDate)
        #ahtml = template.render(species=aoi.species, shape=aoi.poly,aoi=aoi)
        with open(outfile, 'w') as f:
            f.write(ahtml)
        #the last hurah!
        # arcpy.SetParameterAsText(1, outfile)
        return outfile

class oracle_pyqgis:
    ''' oracle_pyqgis has utilities for creating qgsVectorLayer objects for loading into QGIS
    constructor (database: str,
            host: str,
            user: str,
            port: int,
            password: str)
    '''
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

    def open_db_connection(self):
        ''' open_db_connection creates and opens a db connection to the oracle database
        '''
        driver ="QOCISPATIAL"
        conn_name = "bcgw_conn"
        if not QSqlDatabase.contains(conn_name):
            self.db = QSqlDatabase.addDatabase(driver,conn_name)
        else:
            self.db = QSqlDatabase.database(conn_name)
        self.db.setDatabaseName(self.host + "/" + self.database)
        self.db.setUserName(self.user_name) 
        self.db.setPassword(self.user_pass) 
        db_open = self.db.open()
        return db_open
    def close_db_connection(self):
        ''' close_db_connection closes db connection to the oracle database
        '''
        if self.db.isOpen():
            self.db.close()
        
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
