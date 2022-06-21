import os
import sys
import yaml
try:
    from bcgov_qgis_boiler_plate import * # your standalone QGIS module here, or run this script from the Python console inside QGIS
except:
    pass

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
    try:
        i = input("Hit enter to continue with install on default profile or enter profile number: ")
    except: # QGIS console does not support input()
        import PyQt5.QtCore
        import PyQt5.QtGui
        import qgis.core
        import qgis.gui
        import qgis.utils

        from PyQt5.QtWidgets import QInputDialog #this is for your dialogs

        tempTuple = QInputDialog.getText(None, "Select profile" ,"Hit enter to continue with install on default profile or enter profile number: ")
        i = tempTuple[0]
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
    
if os.path.exists('config.yml'): # if running with boilerplate
    config_yml = 'config.yml'
    root = get_from_yaml('application', config_yml)['root']
    if not root:
        root = os.getcwd()
else: # QGIS console will not have script path as current working directory
    from console.console import _console
    install_path = os.path.dirname(_console.console.tabEditorWidget.currentWidget().path)
    config_yml = os.path.join(os.path.dirname(install_path),'config.yml')
    root = install_path
    
s.beginWriteArray('dissect')

s.setValue('root', root) 

defaults = get_from_yaml('default_config', config_yml)
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
print('Settings configured - restart QGIS if currently running')