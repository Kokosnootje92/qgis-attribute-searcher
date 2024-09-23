# -*- coding: utf-8 -*-
"""
        begin                : 2024-09-19
        git sha              : $Format:%H$
        copyright            : (C) 2024 by Leon Cocco
        email                : leon.cocco92@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import QgsFeatureRequest, Qgis, QgsProject, QgsMapLayer
from .resources import *
from .attribute_searcher_id_dialog import AttributeSearcherDockWidget
from .settings_dialog import AttributeSearcherSettingsDialog
import os.path


class AttributeSearcher:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # Initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # Initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'AttributeSearcher_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&AttributeSearcher')

        # Check if the plugin was started for the first time in the current QGIS session
        self.first_start = None
        self.dockwidget = None

        # Declare new instance attributes to manage found features, index, and layer lock
        self.matched_ids = []  # List to store found feature IDs
        self.current_index = 0  # Index to track the current feature being viewed
        self.locked_layer = None  # Variable to store the locked layer
        self.selected_attribute = None  # Variable to store the selected attribute field
        self.search_executed = False  # Flag to track if search has been executed
        self.previous_search_value = ""  # Track previous search value
        self.label_layer_name = None  # Label to display the current layer name

    def tr(self, message):
        """Get the translation for a string using Qt translation API."""
        return QCoreApplication.translate('AttributeSearcher', message)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar."""
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)
        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        icon_path = ':/plugins/AttributeSearcher/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'AttributeSearcher'),
            callback=self.run,
            parent=self.iface.mainWindow())

        # Add settings action
        self.settings_action = QAction("Attribute Searcher Settings", self.iface.mainWindow())
        self.settings_action.triggered.connect(self.open_settings_dialog)
        self.iface.addPluginToMenu(self.menu, self.settings_action)

        self.first_start = True

        # Check user preference for auto-start
        settings = QSettings()
        auto_start = settings.value("AttributeSearcher/auto_start", False, type=bool)
        if auto_start:
            self.run()
        
        QgsProject.instance().layersWillBeRemoved.connect(self.on_layers_removed)
        
    def unload(self):
        """Removes the plugin menu item and icon from the QGIS GUI."""
        if self.dockwidget:
            self.iface.removeDockWidget(self.dockwidget)
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&AttributeSearcher'),
                action)
            self.iface.removeToolBarIcon(action)
        # Remove settings action
        self.iface.removePluginMenu(self.menu, self.settings_action)
        
    def open_settings_dialog(self):
        dialog = AttributeSearcherSettingsDialog()
        dialog.exec_()

    def on_layers_removed(self, layer_ids):
        """Handle layers being removed from the project."""
        # If the locked layer is being removed, unlock it
        if self.locked_layer and self.locked_layer.id() in layer_ids:
            self.locked_layer = None
            self.selected_attribute = None  # Clear the stored attribute field
            self.dockwidget.pushButton_lock_layer.setText("Lock Layer")
            self.iface.messageBar().pushMessage(
                "Info", "Locked layer has been removed. Layer unlocked.", level=Qgis.Info, duration=3)
    
    def run(self):
        """Run method that performs all the real work."""
        if self.first_start:
            self.first_start = False
            self.dockwidget = AttributeSearcherDockWidget()
            self.dockwidget.setWindowTitle("Attribute Searcher")

            # Voeg het dock-widget toe aan de rechterkant
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dockwidget)

            # Connect buttons and other elements
            self.dockwidget.pushButton_search.clicked.connect(self.handle_enter_pressed)
            self.dockwidget.lineEdit_search_id.returnPressed.connect(self.handle_enter_pressed)
            self.dockwidget.pushButton_lock_layer.clicked.connect(self.toggle_layer_lock)

            # Populate attribute dropdown
            self.populate_attribute_dropdown()

            # Connect to layer change event after UI is ready
            self.iface.currentLayerChanged.connect(self.populate_attribute_dropdown)

        # Set the layer name when the dialog is opened.
        self.update_layer_name()

        # Make sure widget is visible
        if self.dockwidget.isHidden():
            self.dockwidget.show()
        else:
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dockwidget)
            self.dockwidget.show()

    def handle_enter_pressed(self):
        """Handle the Enter key press based on whether a search has been executed."""
        current_search_value = self.dockwidget.lineEdit_search_id.text().strip()
        if not self.search_executed or self.previous_search_value != current_search_value:
            # Perform the search when the search hasn't been executed or search value has changed
            self.attribute_searcher()
        else:
            # If the search value is the same, navigate to the next feature
            self.select_and_zoom_to_feature()

    def toggle_layer_lock(self):
        """Toggle the lock status of the currently selected layer."""
        if self.locked_layer:
            # Unlock the layer
            self.locked_layer = None
            self.selected_attribute = None  # Clear the stored attribute field when unlocking
            self.dockwidget.pushButton_lock_layer.setText("Lock Layer")
            self.iface.messageBar().pushMessage("Info", "Layer unlocked.", level=Qgis.Info, duration=1)
        else:
            # Lock the current active layer
            self.locked_layer = self.iface.activeLayer()
            if self.locked_layer:
                self.selected_attribute = self.dockwidget.comboBox_attribute.currentText()  # Store the selected attribute
                self.dockwidget.pushButton_lock_layer.setText("Unlock Layer")
                self.iface.messageBar().pushMessage("Info", f"Layer '{self.locked_layer.name()}' locked.", level=Qgis.Info, duration=1) 
            else:
                self.iface.messageBar().pushMessage("Error", "No active layer to lock.", level=Qgis.Warning, duration=3)

    def populate_attribute_dropdown(self):
        """Populate the attribute dropdown with fields from the active vector layer."""
        # Get the layer
        layer = self.locked_layer if self.locked_layer else self.iface.activeLayer()
        if not layer or not isinstance(layer, QgsMapLayer):
            self.dockwidget.comboBox_attribute.clear()
            return

        # Check if the layer is valid
        if not layer.isValid():
            self.dockwidget.comboBox_attribute.clear()
            return

        # Check if the layer is a vector layer
        if layer.type() != layer.VectorLayer:
            self.iface.messageBar().pushMessage(
                "Info", "The selected layer is not a vector layer.", level=Qgis.Warning, duration=3)
            self.dockwidget.comboBox_attribute.clear()
            return

        fields = layer.fields()
        if not fields.count():
            self.iface.messageBar().pushMessage(
                "Info", "The selected vector layer has no attributes.", level=Qgis.Warning, duration=3)
            self.dockwidget.comboBox_attribute.clear()
            return

        # Populate the dropdown with the available field names
        self.dockwidget.comboBox_attribute.clear()
        self.dockwidget.comboBox_attribute.addItems([field.name() for field in fields])

        # Restore the previously selected attribute if available
        if self.selected_attribute and self.selected_attribute in [field.name() for field in fields]:
            self.dockwidget.comboBox_attribute.setCurrentText(self.selected_attribute)

        # Update the layer name when the dropdown is populated
        self.update_layer_name()

    def update_layer_name(self):
        layer = self.locked_layer if self.locked_layer else self.iface.activeLayer()

        # Check if there is a valid layer
        if layer and layer.isValid():
            layer_name = layer.name()  # Fetch the name of the layer
            self.dockwidget.labelLayerName.setText(f"Searching in layer: {layer_name}")
        else:
            self.dockwidget.labelLayerName.setText("No active layer selected.")

    def attribute_searcher(self):
        """Function to search for an attribute in the active layer with partial matching."""
        # Reset state and matched IDs with every new query
        self.matched_ids = []
        self.current_index = 0
        self.search_executed = False

        # Clear any previous selections in the layer
        layer = self.locked_layer if self.locked_layer else self.iface.activeLayer()
        if layer:
            layer.removeSelection()

        search_value = self.dockwidget.lineEdit_search_id.text().strip()
        if not search_value:
            self._show_message("Please enter an ID to search.", level=Qgis.Critical)
            return

        # Use the locked layer if available, otherwise the active layer
        layer = self.locked_layer if self.locked_layer else self.iface.activeLayer()
        if not layer or not layer.fields().count():
            self._show_message("No active layer or no fields available.", level=Qgis.Warning, duration=3)
            return

        # Get the selected attribute field from the dropdown
        attribute_field = self.dockwidget.comboBox_attribute.currentText()
        if not attribute_field:
            self._show_message("Select an attribute field to search.", level=Qgis.Critical)
            return

        # Maak een feature request met LIKE voor gedeeltelijke overeenkomsten
        request = QgsFeatureRequest().setFilterExpression(f'"{attribute_field}" LIKE \'%{search_value}%\'')
        matching_features = layer.getFeatures(request)

        # Verzamel de IDs van de gevonden objecten
        self.matched_ids = [feature.id() for feature in matching_features]
        print(f"New search results: {self.matched_ids}")

        if self.matched_ids:
            self.current_index = 0
            self.select_and_zoom_to_feature(layer)
            self.search_executed = True
            self.previous_search_value = search_value
        else:
            self._show_message(f"No objects found with ID containing '{search_value}'.", level=Qgis.Warning, duration=3)

    def select_and_zoom_to_feature(self, layer=None):
        """Selects and zooms to the current feature based on the current_index."""
        if not self.matched_ids:
            print("No matched IDs to process.")
            return

        # Use the locked layer if available, otherwise use the active layer
        layer = layer or self.locked_layer or self.iface.activeLayer()
        if not layer:
            self._show_message("No active layer found!", level=Qgis.Critical, duration=1)
            return

        print(f"Selecting feature with ID: {self.matched_ids[self.current_index]} at index: {self.current_index}")
        
        # Select only the current feature
        layer.selectByIds([self.matched_ids[self.current_index]])

        # Pan the view to the selected feature
        self.iface.mapCanvas().zoomToSelected(layer)
        
        # Set the view scale to 1:250
        self.iface.mapCanvas().zoomScale(250)

        # Get the attribute value of the current feature
        feature = next(layer.getFeatures(QgsFeatureRequest(self.matched_ids[self.current_index])))
        attribute_value = feature[self.dockwidget.comboBox_attribute.currentText()]

        # Update the label in the dialog with the current value
        self.dockwidget.label_found_value.setText(f"Last Found: {attribute_value}")

        # Provide feedback about the selected feature
        if self.current_index == 0 and self.search_executed:  # Only show loop message if not the first run
            self._show_message(
                f"Looping back to the first object: {self.current_index + 1} of {len(self.matched_ids)}.", level=Qgis.Info, duration=1)
        else:
            self._show_message(
                f"Showing object {self.current_index + 1} of {len(self.matched_ids)}.", level=Qgis.Info, duration=1)

        # Increment the index for the next feature; wrap around if at the end
        self.current_index = (self.current_index + 1) % len(self.matched_ids)

    def _show_message(self, text, level=Qgis.Info, duration=1):
        """Show a message in the QGIS message bar without opening the log window."""
        self.iface.messageBar().pushMessage("Info", text, level=level, duration=duration)