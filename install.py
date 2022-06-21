#%%
import os
import sys
import yaml
from bcgov_qgis_boiler_plate import * # your standalone QGIS module here, or run this script from the Python console inside QGIS
from qgis.core import QgsUserProfileManager

proMgr = QgsUserProfileManager()

# retrieve profiles
APPDATA = os.environ['appdata']
proRoot = os.path.join(APPDATA, 'QGIS/QGIS3/profiles')
proMgr.setRootLocation(proRoot)
defProfileName = proMgr.defaultProfileName() 
allProfiles = proMgr.allProfiles()
print('\n --- Installing dissect --- \n\nCurrent default profile: ', defProfileName)

# select profile to install on
def let_user_pick(options):
    print("Available profiles:")
    for idx, element in enumerate(options):
        print("{}) {}".format(idx + 1, element))
    i = input("Hit enter to continue with install on default profile or enter profile number: ")
    try:
        if 0 < int(i) <= len(options):
            return allProfiles[int(i) - 1]
    except:
        pass
    return defProfileName
options = allProfiles
profileName = let_user_pick(options)
print('Installing to profile: ', profileName)

# modify profile settings
settingsIni = os.path.join(proMgr.rootLocation(), profileName, 'QGIS/QGIS3.ini')
s = QgsSettings(fileName = settingsIni, format = QSettings.IniFormat)

def get_from_yaml(table,config_file):
    with open(config_file, 'r') as file:
        config = yaml.safe_load(file)[table]
    return config

s.beginWriteArray('dissect')

root = get_from_yaml('application', 'config.yml')['root']
if not root:
    root = os.getcwd()
s.setValue('root', root) 

defaults = get_from_yaml('default_config', 'config.yml')
s.setValue('db', defaults['database'])
s.setValue('host', defaults['host'])
s.setValue('port', defaults['port'])
s.setValue('xls_config', defaults['xls_config']) 
s.setValue('outpath', defaults['outpath'])
s.endArray()

# add to QGIS scripts folder list
newFolder = os.path.join(root, 'dissect')
scripts = s.value('Processing/Configuration/SCRIPTS_FOLDERS',newFolder)
scriptFolders = scripts.split(';')
if newFolder not in scriptFolders:
    scriptFolders.append(newFolder)
scriptFolders = ';'.join(scriptFolders)
s.setValue('Processing/Configuration/SCRIPTS_FOLDERS', scriptFolders)

s.sync()
print('Settings configured')