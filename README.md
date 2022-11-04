[![Lifecycle:Experimental](https://img.shields.io/badge/Lifecycle-Experimental-339999)](<Redirect-URL>)
# dissect (formerly qgis-reports-plugin)
A plugin reporting overlapping GIS datasets

## Installation - BC Government Employees
**_GTS Recommended_** - Use Geospatial or ArcGIS 10.8 (BCGW queries are very slow if run locally)
1. Create a new profile in QGIS if desired (Settings/User Profiles/New Profile)
2. In File Explorer, head to `...\script_whse\python\Reporting\In_Progress\dissect` and run `install.bat`
3. When prompted, hit enter or select the QGIS profile you'd like to install on
4. Restart QGIS if necessary

## Installation
1. Download repo
2. Copy `example_config.yml` to the root folder and rename to `config.yml`
3. Modify optional default parameters as desired
4. Run `install.py`:
    - Open QGIS and run the script from the Python Console (`CTRL+ALT+P`): 1) Show editor, 2) Open script, 3) Run script
    ![image](https://user-images.githubusercontent.com/38586679/175171494-0aa1e977-ed1f-49f0-b31d-d0f33d5deee0.png)
    - if you have a standalone QGIS build, simply run `install.bat` (and change `bcgov_qgis_boiler_plate` in `install.py` to your package)
    - in either case, you will be prompted to select a QGIS profile to install on. You can simply press enter to select the default profile.
5. Configure `data_config.xlsx` as desired. 
<!-- TODO - add more explanation on data config. -->

### Optional additional configuration steps
- Modify default parameters in `config.yml` - then run `install.bat/py` again
    - Defaults can also be set in QGIS after install in Settings > Options > Advanced > dissect.
- Modify html `templates` for output reports
- Configure protected tables in `protected.yml`
    - Protected tables will provide only intersect summary stats - geometries will not be exported.

## Usage
1. Start QGIS
2. Add a file that contains your area of interest polygon (or create a new temp layer ![add temporary scratch layer](https://user-images.githubusercontent.com/38586679/177222992-26296bd0-e5fb-4f2f-9a70-5b1aa700de27.png))
3. Open the Processing Toolbox (CTRL+ALT+T) and select `dissect` from Scripts at the bottom of the toolbox

![Processing toolbox](https://user-images.githubusercontent.com/38586679/177223206-ca622e66-5db8-4a51-af80-df61e8caf1df.png)

4. Select your area of interest

![Selecting an AOI](https://user-images.githubusercontent.com/38586679/177374788-f756326c-eb65-4dcc-911e-ab142aeffbf4.png)

5. Add your database credentials (+).  

![Create a new authentication configuration](https://user-images.githubusercontent.com/38586679/177375117-ceb17315-fd07-4aed-805e-bfb7d087aa47.png)

This login will be stored in an encrypted file within your QGIS profile. If you haven't done so previously, you will be asked to set a master password to edit/view stored configurations - this can be whatever you want.

![Setting a master password](https://user-images.githubusercontent.com/38586679/177377128-dd3c051d-5dd7-4f45-b0f0-fd495d348ea5.png)

Give the configuration a name and enter the username and password for the database you are accessing (e.g. BCGW)

![Filling in authentication config](https://user-images.githubusercontent.com/38586679/177375401-11d08a33-5465-414f-835e-d5d317d6bc05.png)

6. If desired, check 'Add overlapping interests to map' to have intersecting features added in QGIS (including all original attributes).

![Add overlapping interests](https://user-images.githubusercontent.com/38586679/177377485-1dd734a9-06f8-44e0-9316-aa52340d783b.png)

7. Run! (Expected runtimes are roughly 2 min for a 100 ha AOI or 8 min for a 10 000 ha AOI with the default Terrestrial Datasets configuration)

## Report output
When complete, the Results Viewer panel should open on the bottom right with a hyperlink directly to the report file. The html report file contains summary statistics as well as geospatial data for all interests (except protected tables, which have summary stats only).

![Results viewer panel](https://user-images.githubusercontent.com/38586679/177389872-c55e4cf4-e0e1-4553-8622-44ad9c951e89.png)

Use the buttons below the map to filter interests by category. Use the 'Draw on map' switch to make interests visible on the map.
![Filter buttons](https://user-images.githubusercontent.com/38586679/200076079-1e62b059-6375-46f4-9bf5-3e257411e5b3.png)

At the bottom of the report page, failed layers, ie data which could not be processed and are not included in the report, are listed. The comment included should provide direction for how to resolve the issue, if possible, or whether perhaps you lack access to the requested data.

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
