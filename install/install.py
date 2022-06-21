#%%
import os
import sys
from bcgov_qgis_boiler_plate import * # your standalone QGIS module here, or run this script from the Python console inside QGIS

from qgis.core import QgsUserProfileManager

proMgr = QgsUserProfileManager()

APPDATA = os.environ['appdata']
proRoot = os.path.join(APPDATA, 'QGIS/QGIS3/profiles')
proMgr.setRootLocation(proRoot)
profileName = proMgr.defaultProfileName() ### will use the profile user has set as default
# profileName = 'default' ### alternatively, use this line to install to 'default' or other named profile
print('Profile name: ', profileName)

settingsIni = os.path.join(proMgr.rootLocation(), profileName, 'QGIS/QGIS3.ini')

s = QgsSettings(fileName = settingsIni, format = QSettings.IniFormat)

s.beginWriteArray('dissect')
# REQUIRED point to dir containing dissect.py, template folder, etc
s.setValue('script_path', 'YOUR_DIR') 

# OPTIONAL define default parameters
s.setValue('db', 'DEFAULT')
s.setValue('host', 'DEFAULT')
s.setValue('port', 'DEFAULT')
s.setValue('xls_config', 'DEFAULT') 
s.setValue('outpath', 'DEFAULT')
s.endArray()

# OPTIONAL add a scripts folder
newFolder = 'YOUR_SCRIPTS_DIR'
scripts = s.value('Processing/Configuration/SCRIPTS_FOLDERS',newFolder)
scriptFolders = scripts.split(';')
print(scriptFolders)
if newFolder not in scriptFolders:
    scriptFolders.append(newFolder)
scriptFolders = ';'.join(scriptFolders)
print(scriptFolders)
s.setValue('Processing/Configuration/SCRIPTS_FOLDERS', scriptFolders)

s.sync()

# %%
