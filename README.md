[![Lifecycle:Experimental](https://img.shields.io/badge/Lifecycle-Experimental-339999)](<Redirect-URL>)
# qgis-reports-plugin
A plugin reporting overlapping GIS datasets

## Installation
1. Place the contents of this repo in QGIS processing scripts folder. 
    - For BC Gov employees working on the GTS, this path will be `C:\Users\<USERNAME>\AppData\Roaming\QGIS\QGIS3\profiles\default\processing\scripts\`
2. Set the environment variable `QENV_CONFIG_PATH` to the repo folder
    - In QGIS: Settings --> Options --> System --> Environment, and then add `QENV_CONFIG_PATH`
3. Configure `data_config.xlsx` as desired. TODO - add more explanation.

### Optional additional configuration steps
4. Create additional environment variables to populate default script parameters:
    - Oracle database name and login: `QENV_DB`, `QENV_DB_USER`, `QENV_DB_PASS`
    - Data configuration path: `QENV_XLS_CONFIG`
    - Report output path: `QENV_OUT`
5. Modify html `templates` for output reports
6. Configure protected tables in `protected.yml` and add to `CONFIG_PATH` folder
    - Protected tables will provide only intersect summary stats - geometries will not be exported.

## Usage
1. Start QGIS
2. Add a file that contains your area of interest <!-- and if needed make a selection from the file.  -->
3. Open the Processing Toolbox (CTRL+ALT+T) and select `dissect_alg` from Scripts at the bottom of the toolbox
    - it may be necessary to reload scripts following installation - click 'Options' (wrench icon) and then OK
4. Select your area of interest layer from the dropdown    <!-- - If your AOI is a selection subset check the 'Use selected features' checkbox -->
5. Select your data configuration .xlsx file (using ... or by typing in path)
6. Fill out your database credentials<!-- 6. Activate the 'Add overlapping interests to QGIS radio' button if desired -->
7. Set output destination
8. Run!

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
