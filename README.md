# qgis-attribute-searcher
This plugin searches for a value in an user-specified attribute through a menu which is docked in the layout window. 
It was originally created for searching IDs of a Basisregistratie Adressen en Gebouwen (BAG) dataset without needing another attribute table window. 
But this can also be used for other purposes. The plugin works by selecting a attribute from the active layer from the built-in dropdown menu. 
After that you can search for values that are in the specific attribute. If it finds a match, you'll get a message and the view pans over to the found object. 
If there is no match, you'll get an error-message. This has only been tested in Windows 11 and QGIS version 3.34 LTR.
