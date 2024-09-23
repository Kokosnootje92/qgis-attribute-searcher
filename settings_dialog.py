from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QCheckBox, QPushButton
from qgis.PyQt.QtCore import QSettings

class AttributeSearcherSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AttributeSearcher settings")
        
        self.layout = QVBoxLayout()
        
        self.startup_checkbox = QCheckBox("Start plugin automatically on QGIS startup")
        self.layout.addWidget(self.startup_checkbox)
        
        # Load the current setting
        settings = QSettings()
        auto_start = settings.value("AttributeSearcher/auto_start", False, type=bool)
        self.startup_checkbox.setChecked(auto_start)
        
        # Add OK and Cancel buttons
        self.button_box = QPushButton("OK")
        self.button_box.clicked.connect(self.accept)
        self.layout.addWidget(self.button_box)
        
        self.setLayout(self.layout)

    def accept(self):
        # Save the setting
        settings = QSettings()
        settings.setValue("AttributeSearcher/auto_start", self.startup_checkbox.isChecked())
        super().accept()
