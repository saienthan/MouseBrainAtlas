# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'PreprocessTool.ui'
#
# Created: Tue Sep  6 12:08:46 2016
#      by: PyQt4 UI code generator 4.10.4
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

try:
    _encoding = QtGui.QApplication.UnicodeUTF8
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig, _encoding)
except AttributeError:
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig)

class Ui_PreprocessGui(object):
    def setupUi(self, PreprocessGui):
        PreprocessGui.setObjectName(_fromUtf8("PreprocessGui"))
        PreprocessGui.resize(1248, 1088)
        self.centralwidget = QtGui.QWidget(PreprocessGui)
        self.centralwidget.setObjectName(_fromUtf8("centralwidget"))
        self.gridLayout_2 = QtGui.QGridLayout(self.centralwidget)
        self.gridLayout_2.setObjectName(_fromUtf8("gridLayout_2"))
        self.verticalLayout_2 = QtGui.QVBoxLayout()
        self.verticalLayout_2.setObjectName(_fromUtf8("verticalLayout_2"))
        self.slide_gview = QtGui.QGraphicsView(self.centralwidget)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.slide_gview.sizePolicy().hasHeightForWidth())
        self.slide_gview.setSizePolicy(sizePolicy)
        self.slide_gview.setMinimumSize(QtCore.QSize(1200, 500))
        self.slide_gview.setMaximumSize(QtCore.QSize(1200, 500))
        self.slide_gview.setObjectName(_fromUtf8("slide_gview"))
        self.verticalLayout_2.addWidget(self.slide_gview)
        self.button_download = QtGui.QPushButton(self.centralwidget)
        self.button_download.setObjectName(_fromUtf8("button_download"))
        self.verticalLayout_2.addWidget(self.button_download)
        self.gridLayout_2.addLayout(self.verticalLayout_2, 0, 0, 1, 1)
        self.verticalLayout = QtGui.QVBoxLayout()
        self.verticalLayout.setObjectName(_fromUtf8("verticalLayout"))
        self.sorted_sections_gview = QtGui.QGraphicsView(self.centralwidget)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.sorted_sections_gview.sizePolicy().hasHeightForWidth())
        self.sorted_sections_gview.setSizePolicy(sizePolicy)
        self.sorted_sections_gview.setMinimumSize(QtCore.QSize(600, 500))
        self.sorted_sections_gview.setObjectName(_fromUtf8("sorted_sections_gview"))
        self.verticalLayout.addWidget(self.sorted_sections_gview)
        self.horizontalLayout_6 = QtGui.QHBoxLayout()
        self.horizontalLayout_6.setObjectName(_fromUtf8("horizontalLayout_6"))
        self.label_sorted_sections_filename = QtGui.QLabel(self.centralwidget)
        self.label_sorted_sections_filename.setObjectName(_fromUtf8("label_sorted_sections_filename"))
        self.horizontalLayout_6.addWidget(self.label_sorted_sections_filename)
        self.label_sorted_sections_index = QtGui.QLabel(self.centralwidget)
        self.label_sorted_sections_index.setObjectName(_fromUtf8("label_sorted_sections_index"))
        self.horizontalLayout_6.addWidget(self.label_sorted_sections_index)
        self.button_edit_transform = QtGui.QPushButton(self.centralwidget)
        self.button_edit_transform.setObjectName(_fromUtf8("button_edit_transform"))
        self.horizontalLayout_6.addWidget(self.button_edit_transform)
        self.button_confirm_alignment = QtGui.QPushButton(self.centralwidget)
        self.button_confirm_alignment.setObjectName(_fromUtf8("button_confirm_alignment"))
        self.horizontalLayout_6.addWidget(self.button_confirm_alignment)
        self.comboBox_show = QtGui.QComboBox(self.centralwidget)
        self.comboBox_show.setObjectName(_fromUtf8("comboBox_show"))
        self.comboBox_show.addItem(_fromUtf8(""))
        self.comboBox_show.addItem(_fromUtf8(""))
        self.comboBox_show.addItem(_fromUtf8(""))
        self.comboBox_show.addItem(_fromUtf8(""))
        self.comboBox_show.addItem(_fromUtf8(""))
        self.horizontalLayout_6.addWidget(self.comboBox_show)
        self.verticalLayout.addLayout(self.horizontalLayout_6)
        self.gridLayout_2.addLayout(self.verticalLayout, 0, 1, 1, 1)
        self.gridLayout = QtGui.QGridLayout()
        self.gridLayout.setObjectName(_fromUtf8("gridLayout"))
        self.section2_gview = QtGui.QGraphicsView(self.centralwidget)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.MinimumExpanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.section2_gview.sizePolicy().hasHeightForWidth())
        self.section2_gview.setSizePolicy(sizePolicy)
        self.section2_gview.setObjectName(_fromUtf8("section2_gview"))
        self.gridLayout.addWidget(self.section2_gview, 0, 1, 1, 1)
        self.horizontalLayout_3 = QtGui.QHBoxLayout()
        self.horizontalLayout_3.setObjectName(_fromUtf8("horizontalLayout_3"))
        self.label_section2_filename = QtGui.QLabel(self.centralwidget)
        self.label_section2_filename.setObjectName(_fromUtf8("label_section2_filename"))
        self.horizontalLayout_3.addWidget(self.label_section2_filename)
        self.label_section2_index = QtGui.QLabel(self.centralwidget)
        self.label_section2_index.setObjectName(_fromUtf8("label_section2_index"))
        self.horizontalLayout_3.addWidget(self.label_section2_index)
        self.gridLayout.addLayout(self.horizontalLayout_3, 1, 1, 1, 1)
        self.horizontalLayout = QtGui.QHBoxLayout()
        self.horizontalLayout.setObjectName(_fromUtf8("horizontalLayout"))
        self.label_section3_filename = QtGui.QLabel(self.centralwidget)
        self.label_section3_filename.setObjectName(_fromUtf8("label_section3_filename"))
        self.horizontalLayout.addWidget(self.label_section3_filename)
        self.label_section3_index = QtGui.QLabel(self.centralwidget)
        self.label_section3_index.setObjectName(_fromUtf8("label_section3_index"))
        self.horizontalLayout.addWidget(self.label_section3_index)
        self.gridLayout.addLayout(self.horizontalLayout, 1, 0, 1, 1)
        self.section1_gview = QtGui.QGraphicsView(self.centralwidget)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.MinimumExpanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.section1_gview.sizePolicy().hasHeightForWidth())
        self.section1_gview.setSizePolicy(sizePolicy)
        self.section1_gview.setObjectName(_fromUtf8("section1_gview"))
        self.gridLayout.addWidget(self.section1_gview, 0, 2, 1, 1)
        self.horizontalLayout_4 = QtGui.QHBoxLayout()
        self.horizontalLayout_4.setObjectName(_fromUtf8("horizontalLayout_4"))
        self.label_section1_filename = QtGui.QLabel(self.centralwidget)
        self.label_section1_filename.setObjectName(_fromUtf8("label_section1_filename"))
        self.horizontalLayout_4.addWidget(self.label_section1_filename)
        self.label_section1_index = QtGui.QLabel(self.centralwidget)
        self.label_section1_index.setObjectName(_fromUtf8("label_section1_index"))
        self.horizontalLayout_4.addWidget(self.label_section1_index)
        self.gridLayout.addLayout(self.horizontalLayout_4, 1, 2, 1, 1)
        self.section3_gview = QtGui.QGraphicsView(self.centralwidget)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.MinimumExpanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.section3_gview.sizePolicy().hasHeightForWidth())
        self.section3_gview.setSizePolicy(sizePolicy)
        self.section3_gview.setObjectName(_fromUtf8("section3_gview"))
        self.gridLayout.addWidget(self.section3_gview, 0, 0, 1, 1)
        self.gridLayout_2.addLayout(self.gridLayout, 1, 0, 1, 2)
        self.button_align = QtGui.QPushButton(self.centralwidget)
        self.button_align.setObjectName(_fromUtf8("button_align"))
        self.gridLayout_2.addWidget(self.button_align, 2, 0, 1, 1)
        self.horizontalLayout_2 = QtGui.QHBoxLayout()
        self.horizontalLayout_2.setObjectName(_fromUtf8("horizontalLayout_2"))
        self.button_sort = QtGui.QPushButton(self.centralwidget)
        self.button_sort.setObjectName(_fromUtf8("button_sort"))
        self.horizontalLayout_2.addWidget(self.button_sort)
        self.button_sort_server = QtGui.QPushButton(self.centralwidget)
        self.button_sort_server.setObjectName(_fromUtf8("button_sort_server"))
        self.horizontalLayout_2.addWidget(self.button_sort_server)
        self.gridLayout_2.addLayout(self.horizontalLayout_2, 3, 0, 1, 1)
        self.button_save = QtGui.QPushButton(self.centralwidget)
        self.button_save.setObjectName(_fromUtf8("button_save"))
        self.gridLayout_2.addWidget(self.button_save, 4, 0, 1, 1)
        PreprocessGui.setCentralWidget(self.centralwidget)
        self.menubar = QtGui.QMenuBar(PreprocessGui)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 1248, 25))
        self.menubar.setObjectName(_fromUtf8("menubar"))
        PreprocessGui.setMenuBar(self.menubar)
        self.statusbar = QtGui.QStatusBar(PreprocessGui)
        self.statusbar.setObjectName(_fromUtf8("statusbar"))
        PreprocessGui.setStatusBar(self.statusbar)

        self.retranslateUi(PreprocessGui)
        QtCore.QMetaObject.connectSlotsByName(PreprocessGui)

    def retranslateUi(self, PreprocessGui):
        PreprocessGui.setWindowTitle(_translate("PreprocessGui", "MainWindow", None))
        self.button_download.setText(_translate("PreprocessGui", "Download Macros and Thumbnails", None))
        self.label_sorted_sections_filename.setText(_translate("PreprocessGui", "TextLabel", None))
        self.label_sorted_sections_index.setText(_translate("PreprocessGui", "TextLabel", None))
        self.button_edit_transform.setText(_translate("PreprocessGui", "Edit Transform", None))
        self.button_confirm_alignment.setText(_translate("PreprocessGui", "Confirm Alignment", None))
        self.comboBox_show.setItemText(0, _translate("PreprocessGui", "Original", None))
        self.comboBox_show.setItemText(1, _translate("PreprocessGui", "Original Aligned", None))
        self.comboBox_show.setItemText(2, _translate("PreprocessGui", "Brainstem Cropped", None))
        self.comboBox_show.setItemText(3, _translate("PreprocessGui", "Mask", None))
        self.comboBox_show.setItemText(4, _translate("PreprocessGui", "Brainstem Cropped Masked", None))
        self.label_section2_filename.setText(_translate("PreprocessGui", "File", None))
        self.label_section2_index.setText(_translate("PreprocessGui", "TextLabel", None))
        self.label_section3_filename.setText(_translate("PreprocessGui", "File", None))
        self.label_section3_index.setText(_translate("PreprocessGui", "TextLabel", None))
        self.label_section1_filename.setText(_translate("PreprocessGui", "File", None))
        self.label_section1_index.setText(_translate("PreprocessGui", "TextLabel", None))
        self.button_align.setText(_translate("PreprocessGui", "Align", None))
        self.button_sort.setText(_translate("PreprocessGui", "Sort Sections", None))
        self.button_sort_server.setText(_translate("PreprocessGui", "Sync to Server", None))
        self.button_save.setText(_translate("PreprocessGui", "Save Slide Position -> Filename", None))


if __name__ == "__main__":
    import sys
    app = QtGui.QApplication(sys.argv)
    PreprocessGui = QtGui.QMainWindow()
    ui = Ui_PreprocessGui()
    ui.setupUi(PreprocessGui)
    PreprocessGui.show()
    sys.exit(app.exec_())

