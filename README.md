[![Lifecycle:Experimental](https://img.shields.io/badge/Lifecycle-Experimental-339999)](<Redirect-URL>)
# qgis-reports-plugin
A plugin reporting overlapping GIS datasets

## Installation
1. Place the contents of this repo in QGIS python plugin folder. 
    - For BC Gov employees working on the GTS, this path will be `C:\Users\<USERNAME>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\`
2. Copy example `app.yml` and edit configuration. `root` is the folder containing the plugin
3. Edit `__init__.py` and set `config_path` to the path to the configuration folder (containing `app.yml`)
4. Configure `data_config.xlsx` as desired. Store this file in the same folder as `app.yml`
5. [Optional] Configure html `templates` for output reports

## Usage
1. Start QGIS (restarting QGIS after installation may be necessary to activate the plugin).
2. Add a file that contains your area of interest and if needed make a selection from the file. 
3. Click the QGIS Report button in the Plugins Toolbar.
4. Select your area of interest layer from the dropdown
    - If your AOI is a selection subset check the 'Use selected features' checkbox
5. Fill out your database credentials
6. Activate the 'Add overlapping interests to QGIS radio' button if desired
7. Use the ... to navigate or just type in the path for your output report file (ending in `.html`)

## Contributing
We encourage contributions. Please see our [CONTRIBUTING](https://github.com/bcgov/gis-pantry/blob/master/CONTRIBUTING.md) guidelines. BC Government employees should also ensure they review [BC Open Source Development Employee Guide](https://github.com/bcgov/BC-Policy-Framework-For-GitHub/blob/master/BC-Open-Source-Development-Employee-Guide/README.md) 
* Contribute tools and plugins into tools, standalone scripts and modules to scripts, and small snips and script examples to recipes.
* Please do your best to document your scripts and provide tool documentation 

## License
    Copyright 2019 BC Provincial Government

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
