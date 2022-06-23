[![Lifecycle:Experimental](https://img.shields.io/badge/Lifecycle-Experimental-339999)](<Redirect-URL>)
# qgis-reports-plugin
A plugin reporting overlapping GIS datasets

## Installation
1. Download repo
2. Copy `example_config.yml` to the root folder and rename to `config.yml`
3. Modify optional default parameters as desired
4. Run `install.py`:
    - Open QGIS and run the script from the Python Console (`CTRL+ALT+P`): 1) Show editor, 2) Open script, 3) Run script
    ![image](https://user-images.githubusercontent.com/38586679/175171494-0aa1e977-ed1f-49f0-b31d-d0f33d5deee0.png)
    - if you have a standalone QGIS build, simply run `install.bat` (and change `bcgov_qgis_boiler_plate` in `install.py` to your package)
5. Configure `data_config.xlsx` as desired. 
<!-- TODO - add more explanation on data config. -->

### Optional additional configuration steps
1. Modify default parameters in `config.yml` - then run `install.bat/py` again
2. Modify html `templates` for output reports
3. Configure protected tables in `protected.yml`
    - Protected tables will provide only intersect summary stats - geometries will not be exported.

## Usage
1. Start QGIS
2. Add a file that contains your area of interest <!-- and if needed make a selection from the file.  -->
3. Open the Processing Toolbox (CTRL+ALT+T) and select `dissect_alg` from Scripts at the bottom of the toolbox
    - it may be necessary to reload scripts following installation - click 'Options' (wrench) and then OK

![Processing tool box - use the wrench to reload scripts](https://user-images.githubusercontent.com/38586679/172197256-375e4987-6d51-44ea-840e-a7e92e742434.png)

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
