#! /usr/bin/env python

import sip
sip.setapi('QVariant', 2) # http://stackoverflow.com/questions/21217399/pyqt4-qtcore-qvariant-object-instead-of-a-string

from matplotlib.backends import qt4_compat
use_pyside = qt4_compat.QT_API == qt4_compat.QT_API_PYSIDE
if use_pyside:
    #print 'Using PySide'
    from PySide.QtCore import *
    from PySide.QtGui import *
else:
    #print 'Using PyQt4'
    from PyQt4.QtCore import *
    from PyQt4.QtGui import *

from ui_PreprocessGui import Ui_PreprocessGui
# from ui_GalleryDialog import Ui_gallery_dialog
from ui_AlignmentGui import Ui_AlignmentGui

import cPickle as pickle

import sys, os
sys.path.append(os.environ['REPO_DIR'] + '/utilities')
from utilities2015 import *
from metadata import *
from data_manager import *

from DataFeeder import ImageDataFeeder
from drawable_gscene import *
from zoomable_browsable_gscene import SimpleGraphicsScene, MultiplePixmapsGraphicsScene

from gui_utilities import *
from web_service import WebService

gray_color_table = [qRgb(i, i, i) for i in range(256)]

class SimpleGraphicsScene4(SimpleGraphicsScene):
    """
    Variant that supports adding points.
    """

    anchor_point_added = pyqtSignal(int)

    def __init__(self, id, gview=None, parent=None):
        super(SimpleGraphicsScene4, self).__init__(id=id, gview=gview, parent=parent)
        self.anchor_circle_items = []
        self.mode = 'idle'

    def show_context_menu(self, pos):
        myMenu = QMenu(self.gview)
        # action_add_anchor_point = myMenu.addAction("Add anchor point")
        selected_action = myMenu.exec_(self.gview.viewport().mapToGlobal(pos))
        # if selected_action == action_add_anchor_point:
        #     self.set_mode('add point')

    def set_mode(self, mode):
        print 'mode', self.mode, '->', mode
        if self.mode == mode:
            return
        self.mode = mode

    def eventFilter(self, obj, event):
        if event.type() == QEvent.GraphicsSceneMousePress:
            pos = event.scenePos()
            x = pos.x()
            y = pos.y()

            if self.mode == 'add point':

                radius = 5

                ellipse = QGraphicsEllipseItemModified2(-radius, -radius, 2*radius, 2*radius, scene=self)
                ellipse.setPos(x, y)
                ellipse.setPen(Qt.red)
                ellipse.setBrush(Qt.red)
                ellipse.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemClipsToShape | QGraphicsItem.ItemSendsGeometryChanges | QGraphicsItem.ItemSendsScenePositionChanges)
                ellipse.setZValue(99)

                self.anchor_circle_items.append(ellipse)

                index = self.anchor_circle_items.index(ellipse)

                label = QGraphicsSimpleTextItem(QString(str(index)), parent=ellipse)
                label.setPos(0,0)
                label.setScale(1)
                label.setBrush(Qt.black)
                label.setZValue(50)

                self.anchor_point_added.emit(index)

        return super(SimpleGraphicsScene4, self).eventFilter(obj, event)

class SimpleGraphicsScene3(SimpleGraphicsScene):
    """
    Variant for sorted section gscene.
    """

    bad_status_changed = pyqtSignal(int)
    first_section_set = pyqtSignal(int)
    last_section_set = pyqtSignal(int)
    anchor_set = pyqtSignal(int)
    # move_forward_requested = pyqtSignal()
    # move_backward_requested = pyqtSignal()
    # edit_transform_requested = pyqtSignal()

    def __init__(self, id, gview=None, parent=None):
        super(SimpleGraphicsScene3, self).__init__(id=id, gview=gview, parent=parent)

        self.bad_status_indicator = QGraphicsSimpleTextItem(QString('X'), scene=self)
        self.bad_status_indicator.setPos(50,50)
        self.bad_status_indicator.setScale(5)
        self.bad_status_indicator.setVisible(False)
        self.bad_status_indicator.setBrush(Qt.red)

        # self.first_section_indicator = QGraphicsSimpleTextItem(QString('FIRST'), scene=self)
        # self.first_section_indicator.setPos(50,50)
        # self.first_section_indicator.setScale(5)
        # self.first_section_indicator.setVisible(False)
        # self.first_section_indicator.setBrush(Qt.red)
        #
        # self.last_section_indicator = QGraphicsSimpleTextItem(QString('LAST'), scene=self)
        # self.last_section_indicator.setPos(50,50)
        # self.last_section_indicator.setScale(5)
        # self.last_section_indicator.setVisible(False)
        # self.last_section_indicator.setBrush(Qt.red)

        self.box = QGraphicsRectItem(100,100,100,100,scene=self)
        self.box.setPen(QPen(Qt.red, 5))
        # self.box.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemClipsToShape | QGraphicsItem.ItemSendsGeometryChanges | QGraphicsItem.ItemSendsScenePositionChanges)
        self.box.setFlags(QGraphicsItem.ItemClipsToShape | QGraphicsItem.ItemSendsGeometryChanges)
        self.box.setVisible(False)

        self.corners = {}
        radius = 20
        for c in ['ll', 'lr', 'ul', 'ur']:
            ellipse = QGraphicsEllipseItemModified3(-radius, -radius, 2*radius, 2*radius, scene=self)
            if c == 'll':
                ellipse.setPos(200,100)
            elif c == 'lr':
                ellipse.setPos(200,200)
            elif c == 'ul':
                ellipse.setPos(100,100)
            elif c == 'ur':
                ellipse.setPos(100,200)

            ellipse.setPen(Qt.red)
            ellipse.setBrush(Qt.red)
            ellipse.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemClipsToShape | QGraphicsItem.ItemSendsGeometryChanges | QGraphicsItem.ItemSendsScenePositionChanges)
            # ellipse.setZValue(99)
            ellipse.setVisible(False)
            ellipse.signal_emitter.moved.connect(self.corner_moved)
            ellipse.signal_emitter.pressed.connect(self.corner_pressed)
            ellipse.signal_emitter.released.connect(self.corner_released)
            self.corners[c] = ellipse

        self.serving_ellipse = None

    def corner_pressed(self, ellipse):
        self.serving_ellipse = ellipse

    def corner_released(self, ellipse):
        self.serving_ellipse = None

    def corner_moved(self, ellipse, new_x, new_y):

        if self.serving_ellipse is not None and self.serving_ellipse != ellipse:
            return

        self.serving_ellipse = ellipse

        corner_label = self.corners.keys()[self.corners.values().index(ellipse)]
        if corner_label == 'll':
            self.corners['lr'].setY(new_y)
            self.corners['ul'].setX(new_x)
        elif corner_label == 'lr':
            self.corners['ll'].setY(new_y)
            self.corners['ur'].setX(new_x)
        elif corner_label == 'ul':
            self.corners['ur'].setY(new_y)
            self.corners['ll'].setX(new_x)
        elif corner_label == 'ur':
            self.corners['ul'].setY(new_y)
            self.corners['lr'].setX(new_x)

        ul_pos = self.corners['ul'].scenePos()
        lr_pos = self.corners['lr'].scenePos()

        self.box.setRect(ul_pos.x(), ul_pos.y(), lr_pos.x()-ul_pos.x(), lr_pos.y()-ul_pos.y())

    def set_box(self, xmin, xmax, ymin, ymax):
        for c in self.corners.values():
            c.setVisible(True)
        self.corners['ul'].setPos(xmin, ymin)
        self.corners['ur'].setPos(xmax, ymin)
        self.corners['ll'].setPos(xmin, ymax)
        self.corners['lr'].setPos(xmax, ymax)

        self.box.setVisible(True)
        self.box.setRect(xmin, ymin, xmax-xmin, ymax-ymin)

    def set_bad_sections(self, secs):
        self.bad_sections = secs

    def show_context_menu(self, pos):
        myMenu = QMenu(self.gview)

        is_bad = self.active_section in self.bad_sections
        action_setBad = myMenu.addAction("Unmark as Bad" if is_bad else "Mark as Bad")
        # action_moveForward = myMenu.addAction("Move forward")
        # action_moveBackward = myMenu.addAction("Move backward")

        box_on = self.box.isVisible()
        action_toggleBox = myMenu.addAction("Show crop box" if not box_on else 'Hide crop box')
        # action_edit_transform = myMenu.addAction("Edit transform to previous")

        action_setFirst = myMenu.addAction("Set as first")
        action_setLast = myMenu.addAction("Set as last")
        action_setAnchor = myMenu.addAction("Set as anchor")

        selected_action = myMenu.exec_(self.gview.viewport().mapToGlobal(pos))

        if selected_action == action_setBad:
            if is_bad:
                self.bad_status_indicator.setVisible(False)
                self.bad_status_changed.emit(0)
            else:
                self.bad_status_indicator.setVisible(True)
                self.bad_status_changed.emit(1)
        elif selected_action == action_toggleBox:
            self.box.setVisible(not box_on)
            for el in self.corners.values():
                el.setVisible(not box_on)
        elif selected_action == action_setFirst:
            self.first_section_set.emit(self.active_section)
            # self.first_section_indicator.setVisible(True)
        elif selected_action == action_setLast:
            self.last_section_set.emit(self.active_section)
            # self.last_section = self.active_section
            # self.status_updated.emit('LAST')
            # self.last_section_indicator.setVisible(True)
        elif selected_action == action_setAnchor:
            self.anchor_set.emit(self.active_section)

        # elif selected_action == action_moveForward:
        #     self.move_forward_requested.emit()
        # elif selected_action == action_moveBackward:
        #     self.move_backward_requested.emit()
        # elif selected_action == action_edit_transform:
        #     self.edit_transform_requested.emit()

    def set_active_i(self, i, emit_changed_signal=True):
        super(SimpleGraphicsScene3, self).set_active_i(i, emit_changed_signal=True)
        self.bad_status_indicator.setVisible(self.active_section in self.bad_sections)

        # self.first_section_indicator.setVisible(self.active_section == self.first_section)
        # self.last_section_indicator.setVisible(self.active_section == self.last_section)


class SimpleGraphicsScene2(SimpleGraphicsScene):
    """
    Variant for slide position gscenes.
    """

    status_updated = pyqtSignal(int, str)
    send_to_sorted_requested = pyqtSignal(int)

    def __init__(self, id, gview=None, parent=None):
        super(SimpleGraphicsScene2, self).__init__(id=id, gview=gview, parent=parent)

    def show_context_menu(self, pos):
        myMenu = QMenu(self.gview)

        setStatus_menu = QMenu("Set to", myMenu)
        myMenu.addMenu(setStatus_menu)
        action_setNormal = setStatus_menu.addAction('Normal')
        action_setRescan = setStatus_menu.addAction('Rescan')
        action_setPlaceholder = setStatus_menu.addAction('Placeholder')
        action_setNonexisting = setStatus_menu.addAction('Nonexisting')
        actions_setStatus = {action_setNormal: 'Normal', action_setRescan: 'Rescan',
                            action_setPlaceholder: 'Placeholder', action_setNonexisting: 'Nonexisting'}

        action_sendToSorted = myMenu.addAction("Send to sorted scene")

        selected_action = myMenu.exec_(self.gview.viewport().mapToGlobal(pos))

        if selected_action in actions_setStatus:
            status = actions_setStatus[selected_action]
            self.status_updated.emit(self.id, status)
        elif selected_action == action_sendToSorted:
            self.send_to_sorted_requested.emit(self.id)


from subprocess import check_output
from joblib import Parallel, delayed

def identify_shape(img_fp):
    return map(int, check_output("identify -format %%Wx%%H %s" % img_fp, shell=True).split('x'))

# Use the third method in http://pyqt.sourceforge.net/Docs/PyQt4/designer.html
class PreprocessGUI(QMainWindow, Ui_PreprocessGui):
    def __init__(self, parent=None, stack=None):
        """
        Initialization of preprocessing tool.
        """
        # self.app = QApplication(sys.argv)
        QMainWindow.__init__(self, parent)

        self.setupUi(self)

        self.stack = stack

        # for fluorescent stack, tif is 16 bit (not visible in GUI), png is 8 bit
        if self.stack == 'MD635':
            self.tb_fmt = 'png'
            self.pad_bg_color = 'black'
        else:
            self.tb_fmt = 'tif'
            self.pad_bg_color = 'white'

        self.stack_data_dir = os.path.join(thumbnail_data_dir, stack)
        self.stack_data_dir_remote = os.path.join(remote_thumbnail_data_dir, stack)
        self.remote_host = REMOTE_HOST
        self.remote_data_store = REMOTE_DATA_STORE
        self.identity_file = IDENTITY_FILE

        self.web_service = WebService()

        ###############################################

        self.slide_gscene = SimpleGraphicsScene(id='section', gview=self.slide_gview)
        self.slide_gview.setScene(self.slide_gscene)

        # slide_indices = ['N11, N12, IHC28']
        macros_dir = os.path.join(RAW_DATA_DIR, 'macros/%(stack)s/' % {'stack': self.stack})

        slide_filenames = {}
        import re
        for fn in os.listdir(macros_dir):
            res = re.findall('^(.*?)\s?-\s?(F|N|IHC)\s*([0-9]+)\s?-\s?(.*?) (.*?)_macro.jpg$', fn)
            if len(res) > 0:
                _, prefix, slide_num, date, hour = res[0]
            else:
                res = re.findall('^macro_(.*?)-(F|N|IHC)([0-9]+)-(.*?)-(.*?).jpg$', fn)
                if len(res) > 0:
                    _, prefix, slide_num, date, hour = res[0]
                else:
                    continue
            slide_filenames[prefix + '_%d' % int(slide_num)] = fn

        create_if_not_exists(self.stack_data_dir)
        with open(self.stack_data_dir + '/' + self.stack + '_slide_list.txt', 'w') as f:
            for slide_name, fn in sorted(slide_filenames.items(), key=lambda x: int(x[0].split('_')[1])):
                f.write(slide_name + ' ' + fn + '\n')

        with open(self.stack_data_dir + '/' + self.stack + '_missing_slide_list.txt', 'w') as f:
            all_IHC_slide_indices = [int(k.split('_')[1]) for k in slide_filenames.keys() if k.startswith('IHC')]
            if len(all_IHC_slide_indices) > 0:
                max_index = np.max(all_IHC_slide_indices)
                min_index = np.min(all_IHC_slide_indices)
                missing_IHC_indices = set(range(min_index, max_index+1)) - set(all_IHC_slide_indices)
            else:
                missing_IHC_indices = []

            all_N_slide_indices = [int(k.split('_')[1]) for k in slide_filenames.keys() if k.startswith('N')]
            if len(all_N_slide_indices) > 0:
                max_index = np.max(all_N_slide_indices)
                min_index = np.min(all_N_slide_indices)
                missing_N_indices = set(range(min_index, max_index+1)) - set(all_N_slide_indices)
            else:
                missing_N_indices = []

            f.write(' '.join(sorted(['IHC_%d' % i for i in missing_IHC_indices], key=lambda x: int(x.split('_')[1])) + \
                            sorted(['N_%d' % i for i in missing_N_indices], key=lambda x: int(x.split('_')[1]))))

        # print sorted(slide_filenames.keys())

        slide_image_feeder = ImageDataFeeder('image feeder', stack=self.stack, sections=sorted(sorted(slide_filenames.keys(), reverse=True), key=lambda slide_name: int(slide_name.split('_')[1])),
                                            use_data_manager=False)
        # slide_image_feeder.set_orientation(stack_orientation[self.stack])
        slide_image_feeder.set_images(labels=slide_filenames.keys(),
                                    filenames=[os.path.join(macros_dir, filename) for filename in slide_filenames.itervalues()],
                                    downsample=32)
        slide_image_feeder.set_downsample_factor(32)

        self.slide_gscene.set_data_feeder(slide_image_feeder)
        self.slide_gscene.set_active_section(sorted(slide_filenames.keys())[0])
        self.slide_gscene.active_image_updated.connect(self.slide_image_updated)

        ################################################

        # self.slide_position_to_fn = defaultdict(lambda: defaultdict(lambda: 'Unknown'))
        self.slide_position_to_fn = {slide_index: {p: 'Unknown' for p in [1,2,3]}
                                        for slide_index in slide_filenames.iterkeys()}

        ###############

        self.thumbnails_dir = os.path.join(RAW_DATA_DIR, '%(stack)s/' % {'stack': self.stack})
        from glob import glob

        self.thumbnail_filenames = defaultdict(lambda: defaultdict(lambda: dict()))
        self.filename_to_slide = {}

        for fp in glob(self.thumbnails_dir+'/*.%s' % self.tb_fmt):
            fn = os.path.splitext(os.path.basename(fp))[0]
            _, prefix, slide_num, date, hour, _, position, index = re.findall('^(.*?)-([A-Z]+)([0-9]+)-(.*?)-(.*?)_(.*?)_([0-9])_([0-9]{4})$', fn)[0]
            # print prefix, slide_num, position, index
            slide_name = prefix + '_%d' % int(slide_num)
            self.filename_to_slide[fn] = slide_name
            self.thumbnail_filenames[slide_name][int(position)][date+'_'+index] = fn

        ################

        self.section1_gscene = SimpleGraphicsScene2(id=1, gview=self.section1_gview)
        self.section1_gview.setScene(self.section1_gscene)
        self.section1_gscene.active_image_updated.connect(self.slide_position_image_updated)
        self.section2_gscene = SimpleGraphicsScene2(id=2, gview=self.section2_gview)
        self.section2_gview.setScene(self.section2_gscene)
        self.section2_gscene.active_image_updated.connect(self.slide_position_image_updated)
        self.section3_gscene = SimpleGraphicsScene2(id=3, gview=self.section3_gview)
        self.section3_gview.setScene(self.section3_gscene)
        self.section3_gscene.active_image_updated.connect(self.slide_position_image_updated)

        self.section1_gscene.status_updated.connect(self.slide_position_status_updated)
        self.section2_gscene.status_updated.connect(self.slide_position_status_updated)
        self.section3_gscene.status_updated.connect(self.slide_position_status_updated)
        self.section1_gscene.send_to_sorted_requested.connect(self.send_to_sorted)
        self.section2_gscene.send_to_sorted_requested.connect(self.send_to_sorted)
        self.section3_gscene.send_to_sorted_requested.connect(self.send_to_sorted)

        self.slide_position_gscenes = {1: self.section1_gscene, 2: self.section2_gscene, 3: self.section3_gscene}

        self.section_image_feeders = {}

        # blank_image_data = np.zeros((800, 500), np.uint8) * 255
        # self.blank_qimage = QImage(blank_image_data.flatten(), 500, 800, 500, QImage.Format_Indexed8)
        # self.blank_qimage.setColorTable(gray_color_table)

        self.placeholder_qimage = QImage(800, 500, QImage.Format_RGB888)
        painter = QPainter(self.placeholder_qimage)
        painter.fillRect(self.placeholder_qimage.rect(), Qt.yellow);
        painter.drawText(self.placeholder_qimage.rect(), Qt.AlignCenter | Qt.AlignVCenter, "Placeholder");

        self.rescan_qimage = QImage(800, 500, QImage.Format_RGB888)
        painter = QPainter(self.rescan_qimage)
        painter.fillRect(self.rescan_qimage.rect(), Qt.green);
        painter.drawText(self.rescan_qimage.rect(), Qt.AlignCenter | Qt.AlignVCenter, "Rescan");

        self.nonexisting_qimage = QImage(800, 500, QImage.Format_RGB888)
        painter = QPainter(self.nonexisting_qimage)
        painter.fillRect(self.nonexisting_qimage.rect(), Qt.white);
        painter.drawText(self.nonexisting_qimage.rect(), Qt.AlignCenter | Qt.AlignVCenter, "Nonexisting");

        for slide_index in slide_filenames.iterkeys():

            filenames = [fn for x in self.thumbnail_filenames[slide_index].values() for fn in x.values()]

            section_image_feeder = ImageDataFeeder('image feeder', stack=self.stack,
                                                    sections=filenames + ['Nonexisting', 'Rescan', 'Placeholder'],
                                                    use_data_manager=False)
            section_image_feeder.set_images(labels=filenames,
                                            filenames=[os.path.join(self.thumbnails_dir, fn + '.' + self.tb_fmt) for fn in filenames],
                                            downsample=32)

            section_image_feeder.set_downsample_factor(32)
            # section_image_feeder.set_orientation(stack_orientation[self.stack])

            # for fn in filenames:
            #     qimage = QImage(os.path.join(self.thumbnails_dir, fn + '.tif'))
            #     section_image_feeder.set_image(qimage, fn)

            section_image_feeder.set_image(self.nonexisting_qimage, 'Nonexisting')
            section_image_feeder.set_image(self.rescan_qimage, 'Rescan')
            section_image_feeder.set_image(self.placeholder_qimage, 'Placeholder')

            self.section_image_feeders[slide_index] = section_image_feeder


        #######################

        self.first_section = 1
        self.last_section = 2


        # self.sorted_filenames = []
        #
        # filename_map_fp = '/home/yuncong/CSHL_data_processed/%(stack)s_filename_map.txt' % {'stack': stack}
        # if os.path.exists(filename_map_fp):
        #     with open(filename_map_fp, 'r') as f:
        #         for line in f.readlines():
        #             fn, sequence_index = line.split()
        #             self.sorted_filenames.append((int(sequence_index), fn))
        #     self.sorted_filenames = [fn for si, fn in sorted(self.sorted_filenames)]

        self.sorted_sections_gscene = SimpleGraphicsScene3(id='sorted', gview=self.sorted_sections_gview)
        self.sorted_sections_gview.setScene(self.sorted_sections_gscene)

        # ordered_image_feeder = ImageDataFeeder('image feeder', stack=self.stack, sections=range(1, len(self.sorted_filenames)+1), use_data_manager=False)
        # ordered_image_feeder.set_downsample_factor(32)
        # ordered_image_feeder.set_orientation(stack_orientation[self.stack])
        #
        # for i, filename in enumerate(self.sorted_filenames):
        #     qimage = QImage(os.path.join(self.thumbnails_dir, filename))
        #     ordered_image_feeder.set_image(qimage, i+1)
        #
        # self.sorted_sections_gscene.set_data_feeder(ordered_image_feeder)
        #
        # self.sorted_sections_gscene.set_active_section(2)
        self.sorted_sections_gscene.active_image_updated.connect(self.sorted_sections_image_updated)
        self.sorted_sections_gscene.bad_status_changed.connect(self.bad_status_changed)
        self.sorted_sections_gscene.first_section_set.connect(self.set_first_section)
        self.sorted_sections_gscene.last_section_set.connect(self.set_last_section)
        self.sorted_sections_gscene.anchor_set.connect(self.set_anchor)

        # self.sorted_sections_gscene.move_forward_requested.connect(self.move_forward)
        # self.sorted_sections_gscene.move_backward_requested.connect(self.move_backward)
        # self.sorted_sections_gscene.edit_transform_requested.connect(self.edit_transform)

        #######################

        self.installEventFilter(self)

        self.comboBox_show.activated.connect(self.show_option_changed)

        self.comboBox_slide_position_adjustment.activated.connect(self.slide_position_adjustment_changed)

        self.button_save_slide_position_map.clicked.connect(self.save)
        self.button_load_slide_position_map.clicked.connect(self.load_slide_position_map)
        self.button_sort.clicked.connect(self.sort)
        self.button_confirm_order.clicked.connect(self.confirm_order)
        self.button_load_sorted_filenames.clicked.connect(self.load_sorted_filenames)
        self.button_save_sorted_filenames.clicked.connect(self.save_sorted_filenames)
        self.button_align.clicked.connect(self.align)
        # self.button_align.setEnabled(False)
        self.button_confirm_alignment.clicked.connect(self.compose)
        self.button_download.clicked.connect(self.download)
        self.button_edit_transform.clicked.connect(self.edit_transform)
        self.button_crop.clicked.connect(self.crop)
        self.button_load_crop.clicked.connect(self.load_crop)
        self.button_save_crop.clicked.connect(self.save_crop)
        self.button_gen_mask.clicked.connect(self.generate_masks)
        self.button_warp_crop_mask.clicked.connect(self.warp_crop_masks)
        self.button_syncWorkstation.clicked.connect(self.send_to_workstation)

        self.button_send_info_gordon.clicked.connect(self.send_info_gordon)
        # self.button_send_info_workstation.clicked.connect(self.send_info_workstation)

        ################################

        self.placeholders = set([])
        self.rescans = set([])

        # self.status_comboBoxes = {1: self.comboBox_status1, 2: self.comboBox_status2, 3: self.comboBox_status3}
        self.labels_slide_position_filename = {1: self.label_section1_filename, 2: self.label_section2_filename, 3: self.label_section3_filename}
        self.labels_slide_position_index = {1: self.label_section1_index, 2: self.label_section2_index, 3: self.label_section3_index}


    # def move_backward(self):
    #
    #     curr_label = self.sorted_sections_gscene.active_section
    #     print 'old index filename', self.sorted_filenames[curr_label-1]
    #
    #     curr_index = self.sorted_sections_gscene.active_i
    #
    #     data_feeder = self.sorted_sections_gscene.data_feeder
    #
    #     if curr_index == 0:
    #         return
    #
    #     new_index = curr_index - 1
    #
    #     # swap two filenames
    #     self.sorted_filenames[new_index-1], self.sorted_filenames[curr_index-1] = self.sorted_filenames[curr_index-1], self.sorted_filenames[new_index-1]
    #
    #     # swap two images in data_feeder queue
    #     image1 = data_feeder.retrive_i(i=curr_index)
    #     image2 = data_feeder.retrive_i(i=new_index)
    #     new_label = data_feeder.all_sections[new_index]
    #     data_feeder.set_image(image1, new_label)
    #     data_feeder.set_image(image2, curr_label)
    #
    #     self.sorted_sections_gscene.set_active_section(new_label)
    #     print 'new index filename', self.sorted_filenames[new_label-1]
    #
    #
    # def move_forward(self):
    #
    #     curr_label = self.sorted_sections_gscene.active_section
    #     print 'old index filename', self.sorted_filenames[curr_label-1]
    #
    #     curr_index = self.sorted_sections_gscene.active_i
    #
    #     data_feeder = self.sorted_sections_gscene.data_feeder
    #
    #     if curr_index == data_feeder.n - 1:
    #         return
    #
    #     new_index = curr_index + 1
    #
    #     # swap two filenames
    #     self.sorted_filenames[new_index-1], self.sorted_filenames[curr_index-1] = self.sorted_filenames[curr_index-1], self.sorted_filenames[new_index-1]
    #
    #     # swap two images in data_feeder queue
    #     image1 = data_feeder.retrive_i(i=curr_index)
    #     image2 = data_feeder.retrive_i(i=new_index)
    #     new_label = data_feeder.all_sections[new_index]
    #     data_feeder.set_image(image1, new_label)
    #     data_feeder.set_image(image2, curr_label)
    #
    #     self.sorted_sections_gscene.set_active_section(new_label)
    #     print 'new index filename', self.sorted_filenames[new_label-1]

    def bad_status_changed(self, is_bad):

        print is_bad

        fn = self.sorted_filenames[self.sorted_sections_gscene.active_section-1]

        slide_name = self.filename_to_slide[fn]
        position = self.slide_position_to_fn[slide_name].keys()[self.slide_position_to_fn[slide_name].values().index(fn)]

        if is_bad > 0:
            self.sorted_filenames[self.sorted_filenames.index(fn)] = 'Placeholder'
            self.set_status(slide_name, position, 'Placeholder')
        else:
            raise Exception('Cannot undo set Bad..')
            self.set_status(slide_name, position, 'Normal')

        self.sorted_sections_gscene.set_bad_sections(self.get_bad_sections())


    def send_to_sorted(self, position):
        slide_name = self.slide_gscene.active_section
        fn = self.slide_position_to_fn[slide_name][position]
        index = self.sorted_filenames.index(fn) + 1
        self.sorted_sections_gscene.set_active_section(index)

    def slide_position_adjustment_changed(self, index):
        adjustment_str = str(self.sender().currentText())
        slide_name = self.slide_gscene.active_section

        def swap_normal_positions(x):
            if x[1] == 'Nonexisting':
                x[2], x[3] = x[3], x[2]
            elif x[3] == 'Nonexisting':
                x[1], x[2] = x[2], x[1]
            else:
                x[3], x[1] = x[1], x[3]

        def adjust(x, status, pos):
            abnormal_statuses = ['Nonexisting', 'Rescan', 'Placeholder']
            if pos == 'right':
                if x[1] in abnormal_statuses:
                    x[1], x[2], x[3] = status, x[2], x[3]
                elif x[2] in abnormal_statuses:
                    x[1], x[2], x[3] = status, x[1], x[3]
                elif x[3] in abnormal_statuses:
                    x[1], x[2], x[3] = status, x[1], x[2]
            elif pos == 'left':
                if x[1] in abnormal_statuses:
                    x[1], x[2], x[3] = x[2], x[3], status
                elif x[2] in abnormal_statuses:
                    x[1], x[2], x[3] = x[1], x[3], status
                elif x[3] in abnormal_statuses:
                    x[1], x[2], x[3] = x[1], x[2], status

        if adjustment_str == 'Reverse positions':

            x = self.slide_position_to_fn[slide_name]

            # if x.values().count('Nonexisting') == 0:

            # if x[1] == 'Nonexisting':
            #     x[2], x[3] = x[3], x[2]
            # elif x[3] == 'Nonexisting':
            #     x[1], x[2] = x[2], x[1]
            # else:
            #     x[3], x[1] = x[1], x[3]
            swap_normal_positions(x)

            for position in [1,2,3]:
                self.set_status(slide_name, position, self.slide_position_to_fn[slide_name][position])

        elif adjustment_str == 'Reverse positions on all slides':
            for sn, x in self.slide_position_to_fn.iteritems():
                # if x.values().count('Nonexisting') == 0:
                # if x[1] == 'Nonexisting':
                #     x[2], x[3] = x[3], x[2]
                # elif x[3] == 'Nonexisting':
                #     x[1], x[2] = x[2], x[1]
                # else:
                #     x[3], x[1] = x[1], x[3]
                swap_normal_positions(x)

                for pos in [1,2,3]:
                    self.set_status(sn, pos, self.slide_position_to_fn[sn][pos])

        elif adjustment_str == 'Reverse positions on all IHC slides':
            for sn, x in self.slide_position_to_fn.iteritems():
                if sn.startswith('IHC'):
                    # if x[1] == 'Nonexisting':
                    #     x[2], x[3] = x[3], x[2]
                    # elif x[3] == 'Nonexisting':
                    #     x[1], x[2] = x[2], x[1]
                    # else:
                    #     x[3], x[1] = x[1], x[3]
                    swap_normal_positions(x)

                    for pos in [1,2,3]:
                        self.set_status(sn, pos, self.slide_position_to_fn[sn][pos])

        elif adjustment_str == 'Reverse positions on all N slides':
            for sn, x in self.slide_position_to_fn.iteritems():
                # if sn.startswith('N') and x.values().count('Nonexisting') == 0:
                if sn.startswith('N'):
                    # print sn, x
                    swap_normal_positions(x)

                    # if x[1] == 'Nonexisting':
                    #     x[2], x[3] = x[3], x[2]
                    # elif x[3] == 'Nonexisting':
                    #     x[1], x[2] = x[2], x[1]
                    # else:
                    #     x[3], x[1] = x[1], x[3]

                    for pos in [1,2,3]:
                        self.set_status(sn, pos, self.slide_position_to_fn[sn][pos])

        elif adjustment_str == 'Move all nonexisting to left':

            for sn, x in self.slide_position_to_fn.iteritems():

                if x.values().count('Nonexisting') == 1:

                    adjust(x, 'Nonexisting', 'left')

                    # if x[1] in ['Nonexisting', 'Rescan', 'Placeholder']:
                    #     x[1], x[2], x[3] = x[2], x[3], 'Nonexisting'
                    # elif x[2] in ['Nonexisting', 'Rescan', 'Placeholder']:
                    #     x[1], x[2], x[3] = x[1], x[3], 'Nonexisting'
                    # elif x[3] in ['Nonexisting', 'Rescan', 'Placeholder']:
                    #     x[1], x[2], x[3] = x[1], x[2], 'Nonexisting'

                    for pos in [1,2,3]:
                        self.set_status(sn, pos, self.slide_position_to_fn[sn][pos])

        elif adjustment_str == 'Move all nonexisting to right':

            for sn, x in self.slide_position_to_fn.iteritems():

                if x.values().count('Nonexisting') == 1:
                    adjust(x, 'Nonexisting', 'right')

                    # if x[1] in ['Nonexisting', 'Rescan', 'Placeholder']:
                    #     x[1], x[2], x[3] = 'Nonexisting', x[2], x[3]
                    # elif x[2] in ['Nonexisting', 'Rescan', 'Placeholder']:
                    #     x[1], x[2], x[3] = 'Nonexisting', x[1], x[3]
                    # elif x[3] in ['Nonexisting', 'Rescan', 'Placeholder']:
                    #     x[1], x[2], x[3] = 'Nonexisting', x[1], x[2]

                    for pos in [1,2,3]:
                        self.set_status(sn, pos, self.slide_position_to_fn[sn][pos])
        else:
            x = self.slide_position_to_fn[slide_name]
            assert x.values().count('Nonexisting') == 1

            if adjustment_str == 'Move placeholder to right':
                adjust(x, 'Placeholder', 'right')
            elif adjustment_str == 'Move rescan to right':
                adjust(x, 'Rescan', 'right')
            elif adjustment_str == 'Move nonexisting to right':
                adjust(x, 'Nonexisting', 'right')
            elif adjustment_str == 'Move placeholder to left':
                adjust(x, 'Placeholder', 'left')
            elif adjustment_str == 'Move rescan to left':
                adjust(x, 'Rescan', 'left')
            elif adjustment_str == 'Move nonexisting to left':
                adjust(x, 'Nonexisting', 'left')

            for position in [1,2,3]:
                self.set_status(slide_name, position, self.slide_position_to_fn[slide_name][position])

    def slide_position_status_updated(self, position, status):
        print 'slide_position_status_updated:', position, status
        slide_name = self.slide_gscene.active_section
        # position = self.slide_position_gscenes[position].active_section
        if status == 'Normal':
            if position in self.thumbnail_filenames[slide_name]:
                newest_fn = sorted(self.thumbnail_filenames[slide_name][position].items())[-1][1]
                self.set_status(slide_name, position, newest_fn)
            else:
                arbitrary_image = self.thumbnail_filenames[slide_name].values()[0].values()[0]
                self.set_status(slide_name, position, arbitrary_image)
        else:
            self.set_status(slide_name, position, str(status))



    def load_crop(self):

        self.set_show_option('aligned')

        with open(os.path.join(thumbnail_data_dir, '%(stack)s/%(stack)s_cropbox.txt' % {'stack': self.stack}), 'r') as f:
            ul_x, lr_x, ul_y, lr_y, self.first_section, self.last_section = map(int, f.readline().split())
            self.sorted_sections_gscene.set_box(ul_x, lr_x, ul_y, lr_y)
            print ul_x, lr_x, ul_y, lr_y, self.first_section, self.last_section


    def save_crop(self):
        ul_pos = self.sorted_sections_gscene.corners['ul'].scenePos()
        lr_pos = self.sorted_sections_gscene.corners['lr'].scenePos()
        ul_x = int(ul_pos.x())
        ul_y = int(ul_pos.y())
        lr_x = int(lr_pos.x())
        lr_y = int(lr_pos.y())

        # If not set yet.
        if ul_x == 100 and ul_y == 100 and lr_x == 200 and lr_y == 200:
            return

        with open(os.path.join(thumbnail_data_dir, '%(stack)s/%(stack)s_cropbox.txt' % {'stack': self.stack}, 'w')) as f:
            f.write('%d %d %d %d %d %d' % (ul_x, lr_x, ul_y, lr_y, self.first_section, self.last_section))

    def crop(self):
        ## Note that in cropbox, xmax, ymax are not included, so w = xmax-xmin, instead of xmax-xmin+1

        self.save_crop()

        ul_pos = self.sorted_sections_gscene.corners['ul'].scenePos()
        lr_pos = self.sorted_sections_gscene.corners['lr'].scenePos()
        ul_x = int(ul_pos.x())
        ul_y = int(ul_pos.y())
        lr_x = int(lr_pos.x())
        lr_y = int(lr_pos.y())

        self.web_service.convert_to_request('crop', stack=self.stack, x=ul_x, y=ul_y, w=lr_x+1-ul_x, h=lr_y+1-ul_y,
                                            f=self.first_section, l=self.last_section, anchor_fn=self.anchor_fn,
                                            filenames=self.get_valid_sorted_filenames(),
                                            first_fn=self.sorted_filenames[self.first_section-1],
                                            last_fn=self.sorted_filenames[self.last_section-1],
                                            pad_bg_color=self.pad_bg_color)

        # Download unsorted thumbnail cropped images
        self.statusBar().showMessage('Downloading aligned cropped thumbnail images ...')

        execute_command(('ssh %(identity_file)s %(remote_host)s \"cd %(remote_data_dir)s && tar -I pigz -cf %(stack)s_thumbnail_unsorted_alignedTo_%(anchor_fn)s_cropped.tar.gz %(stack)s_thumbnail_unsorted_alignedTo_%(anchor_fn)s_cropped/*.tif\" && '
                        'scp %(identity_file)s %(remote_data_store)s:%(remote_data_dir)s/%(stack)s_thumbnail_unsorted_alignedTo_%(anchor_fn)s_cropped.tar.gz %(local_data_dir)s/ &&'
                        'ssh %(identity_file)s %(remote_host)s rm %(remote_data_dir)s/%(stack)s_thumbnail_unsorted_alignedTo_%(anchor_fn)s_cropped.tar.gz &&'
                        'cd %(local_data_dir)s && rm -rf %(stack)s_thumbnail_unsorted_alignedTo_%(anchor_fn)s_cropped && tar -xf %(stack)s_thumbnail_unsorted_alignedTo_%(anchor_fn)s_cropped.tar.gz && rm %(stack)s_thumbnail_unsorted_alignedTo_%(anchor_fn)s_cropped.tar.gz' ) % \
                        dict(remote_data_dir=self.stack_data_dir_remote,
                            local_data_dir=self.stack_data_dir,
                            identity_file=self.identity_file,
                            remote_data_store=self.remote_data_store,
                            remote_host=self.remote_host,
                            stack=self.stack,
                            anchor_fn=self.anchor_fn))

    def edit_transform(self):

        self.alignment_ui = Ui_AlignmentGui()
        self.alignment_gui = QDialog(self)
        self.alignment_ui.setupUi(self.alignment_gui)

        self.alignment_ui.button_anchor.clicked.connect(self.add_anchor_pair_clicked)
        self.alignment_ui.button_upload_transform.clicked.connect(self.upload_custom_transform)

        self.valid_section_filenames = [fn for fn in self.sorted_filenames if fn != 'Placeholder' and fn != 'Rescan']
        self.valid_section_indices = [self.sorted_filenames.index(fn)+1 for fn in self.valid_section_filenames]

        valid_sections_feeder = ImageDataFeeder('valid image feeder', stack=self.stack, sections=self.valid_section_indices, use_data_manager=False)
        valid_sections_feeder.set_images(self.valid_section_indices, [os.path.join(self.thumbnails_dir, fn + '.' + self.tb_fmt) for fn in self.valid_section_filenames], downsample=32)
        valid_sections_feeder.set_downsample_factor(32)

        self.curr_gscene = SimpleGraphicsScene4(id='current', gview=self.alignment_ui.curr_gview)
        self.alignment_ui.curr_gview.setScene(self.curr_gscene)
        self.curr_gscene.set_data_feeder(valid_sections_feeder)
        self.curr_gscene.set_active_i(1)
        self.curr_gscene.active_image_updated.connect(self.current_section_image_changed)
        self.curr_gscene.anchor_point_added.connect(self.anchor_point_added)

        self.prev_gscene = SimpleGraphicsScene4(id='previous', gview=self.alignment_ui.prev_gview)
        self.alignment_ui.prev_gview.setScene(self.prev_gscene)
        self.prev_gscene.set_data_feeder(valid_sections_feeder)
        self.prev_gscene.set_active_i(0)
        self.prev_gscene.active_image_updated.connect(self.previous_section_image_changed)
        self.prev_gscene.anchor_point_added.connect(self.anchor_point_added)

        # transformed_image_filenames = [self.stack_data_dir + '/%(stack)s_elastix_output/%(curr_fn)s_to_%(prev_fn)s/result.0.tif' % \
        #                             {'stack': self.stack, 'curr_fn': self.valid_section_filenames[i], 'prev_fn': self.valid_section_filenames[i-1]}
        #                             for i in range(len(self.valid_section_indices))]

        transformed_image_filenames = []
        for i in range(len(self.valid_section_indices)):

            custom_aligned_image_fn = self.stack_data_dir + '/%(stack)s_custom_transforms/%(curr_fn)s_to_%(prev_fn)s/%(curr_fn)s_alignedTo_%(prev_fn)s.tif' % \
            {'stack': self.stack, 'curr_fn': self.valid_section_filenames[i], 'prev_fn': self.valid_section_filenames[i-1]}

            print custom_aligned_image_fn

            if os.path.exists(custom_aligned_image_fn):
                sys.stderr.write('Load custom transform image. %s\n' % custom_aligned_image_fn)
                transformed_image_filenames.append(custom_aligned_image_fn)
            else:
                fn = self.stack_data_dir + '/%(stack)s_elastix_output/%(curr_fn)s_to_%(prev_fn)s/result.0.tif' % \
                {'stack': self.stack, 'curr_fn': self.valid_section_filenames[i], 'prev_fn': self.valid_section_filenames[i-1]}
                transformed_image_filenames.append(fn)

        # aligned_images_feeder_labels = valid_section_indices[1:]
        transformed_images_feeder = ImageDataFeeder('aligned image feeder', stack=self.stack,
                                                sections=self.valid_section_indices, use_data_manager=False)
        transformed_images_feeder.set_images(self.valid_section_indices, transformed_image_filenames, downsample=32, load_with_cv2=True)
        transformed_images_feeder.set_downsample_factor(32)

        self.aligned_gscene = MultiplePixmapsGraphicsScene(id='aligned', pixmap_labels=['moving', 'fixed'], gview=self.alignment_ui.aligned_gview)
        self.alignment_ui.aligned_gview.setScene(self.aligned_gscene)
        self.aligned_gscene.set_data_feeder(transformed_images_feeder, 'moving')
        self.aligned_gscene.set_data_feeder(valid_sections_feeder, 'fixed')
        self.aligned_gscene.set_active_indices({'moving': 1, 'fixed': 0})
        self.aligned_gscene.set_opacity('moving', .8)
        self.aligned_gscene.set_opacity('fixed', .8)
        self.aligned_gscene.active_image_updated.connect(self.aligned_image_changed)

        self.alignment_gui.show()

    def upload_custom_transform(self):
        curr_section_fn = self.sorted_filenames[self.valid_section_indices[self.curr_gscene.active_i]-1]
        prev_section_fn = self.sorted_filenames[self.valid_section_indices[self.prev_gscene.active_i]-1]

        custom_tf_fn = os.path.join(self.stack_data_dir, self.stack+'_custom_transforms', curr_section_fn + '_to_' + prev_section_fn, curr_section_fn + '_to_' + prev_section_fn + '_customTransform.txt')
        with open(custom_tf_fn, 'r') as f:
            t11, t12, t13, t21, t22, t23 = map(float, f.readline().split())

        prev_img_w, prev_img_h = map(int, check_output("identify -format %%Wx%%H %(raw_data_dir)s/%(stack)s/%(prev_fn)s.%(tb_fmt)s" %dict(stack=self.stack, prev_fn=prev_section_fn, tb_fmt=self.tb_fmt, raw_data_dir=RAW_DATA_DIR),
                                            shell=True).split('x'))

        output_image_fn = os.path.join(self.stack_data_dir, '%(stack)s_custom_transforms/%(curr_fn)s_to_%(prev_fn)s/%(curr_fn)s_alignedTo_%(prev_fn)s.tif' % \
                        dict(stack=self.stack,
                        curr_fn=curr_section_fn,
                        prev_fn=prev_section_fn) )

        execute_command("convert %(raw_data_dir)s/%(stack)s/%(curr_fn)s.%(tb_fmt)s -virtual-pixel background +distort AffineProjection '%(sx)f,%(rx)f,%(ry)f,%(sy)f,%(tx)f,%(ty)f' -crop %(w)sx%(h)s%(x)s%(y)s\! -flatten -compress lzw %(output_fn)s" %\
        dict(stack=self.stack,
            curr_fn=curr_section_fn,
            output_fn=output_image_fn,
            tb_fmt=self.tb_fmt,
            sx=t11,
            sy=t22,
            rx=t21,
            ry=t12,
            tx=t13,
            ty=t23,
            w=prev_img_w,
            h=prev_img_h,
            x='+0',
            y='+0',
            raw_data_dir=RAW_DATA_DIR))

        execute_command(('ssh %(identity_file)s %(remote_host)s mkdir %(stack_data_dir_remote)s/%(stack)s_custom_transforms; '
                        'scp -r %(stack_data_dir)s/%(stack)s_custom_transforms/%(curr_fn)s_to_%(prev_fn)s %(identity_file)s %(remote_data_store)s:%(stack_data_dir_remote)s/%(stack)s_custom_transforms/') %\
                        dict(stack_data_dir=self.stack_data_dir,
                            stack_data_dir_remote=self.stack_data_dir_remote,
                            stack=self.stack,
                            identity_file=self.identity_file,
                            remote_data_store=self.remote_data_store,
                            remote_host=self.remote_host,
                            curr_fn=curr_section_fn,
                            prev_fn=prev_section_fn))



    def add_anchor_pair_clicked(self):
        self.curr_gscene.set_mode('add point')
        self.prev_gscene.set_mode('add point')
        self.current_section_anchor_received = False
        self.previous_section_anchor_received = False
        self.alignment_ui.button_anchor.setEnabled(False)

    def anchor_point_added(self, index):
        gscene_id = self.sender().id
        if gscene_id == 'current':
            self.current_section_anchor_received = True
            # self.curr_gscene.anchor_points.index
        elif gscene_id == 'previous':
            self.previous_section_anchor_received = True

        if self.current_section_anchor_received and self.previous_section_anchor_received:
            self.curr_gscene.set_mode('idle')
            self.prev_gscene.set_mode('idle')
            self.current_section_anchor_received = False
            self.previous_section_anchor_received = False
            self.alignment_ui.button_anchor.setEnabled(True)

            curr_points = []
            for i, c in enumerate(self.curr_gscene.anchor_circle_items):
                pos = c.scenePos()
                curr_points.append((pos.x(), pos.y()))

            prev_points = []
            for i, c in enumerate(self.prev_gscene.anchor_circle_items):
                pos = c.scenePos()
                prev_points.append((pos.x(), pos.y()))

            print self.curr_gscene.active_section, np.array(curr_points)
            print self.prev_gscene.active_section, np.array(prev_points)

            curr_points = np.array(curr_points)
            prev_points = np.array(prev_points)
            curr_centroid = curr_points.mean(axis=0)
            prev_centroid = prev_points.mean(axis=0)
            curr_points0 = curr_points - curr_centroid
            prev_points0 = prev_points - prev_centroid

            H = np.dot(curr_points0.T, prev_points0)
            U, S, VT = np.linalg.svd(H)
            R = np.dot(VT.T, U.T)

            t = -np.dot(R, curr_centroid) + prev_centroid

            print R, t

            curr_section_fn = self.sorted_filenames[self.valid_section_indices[self.curr_gscene.active_i]-1]
            prev_section_fn = self.sorted_filenames[self.valid_section_indices[self.prev_gscene.active_i]-1]

            create_if_not_exists(self.stack_data_dir + '/%(stack)s_custom_transforms/%(curr_fn)s_to_%(prev_fn)s/' % \
                                dict(stack=self.stack,
                                    curr_fn=curr_section_fn,
                                    prev_fn=prev_section_fn))

            with open(self.stack_data_dir + '/%(stack)s_custom_transforms/%(curr_fn)s_to_%(prev_fn)s/%(curr_fn)s_to_%(prev_fn)s_customTransform.txt' %\
                        dict(stack=self.stack,
                            curr_fn=curr_section_fn,
                            prev_fn=prev_section_fn), 'w') as f:
                f.write('%f %f %f %f %f %f\n' % (R[0,0], R[0,1], t[0], R[1,0], R[1,1], t[1]))


    def aligned_image_changed(self):
        pass
        # prev_section_idx = self.aligned_gscene.active_indices['fixed']
        # self.curr_gscene.set_active_i(prev_section_idx+1)
        # self.prev_gscene.set_active_i(prev_section_idx)

    def current_section_image_changed(self):
        curr_section_i = self.curr_gscene.active_i
        curr_section_label = self.valid_section_indices[curr_section_i]
        curr_section_fn = self.sorted_filenames[curr_section_label-1]
        self.alignment_ui.label_current_filename.setText(curr_section_fn)
        self.alignment_ui.label_current_index.setText(str(curr_section_label))
        prev_section_i = curr_section_i - 1
        self.prev_gscene.set_active_i(prev_section_i)
        self.aligned_gscene.set_active_indices({'moving': curr_section_i, 'fixed': prev_section_i})

    def previous_section_image_changed(self):
        prev_section_i = self.prev_gscene.active_i
        prev_section_label = self.valid_section_indices[prev_section_i]
        prev_section_fn = self.sorted_filenames[prev_section_label-1]
        self.alignment_ui.label_previous_filename.setText(prev_section_fn)
        self.alignment_ui.label_previous_index.setText(str(prev_section_label))
        curr_section_i = prev_section_i + 1
        self.curr_gscene.set_active_i(curr_section_i)
        self.aligned_gscene.set_active_indices({'moving': curr_section_i, 'fixed': prev_section_i})

    def sort(self):

        prefixes = set([slide_name.split('_')[0] for slide_name in self.slide_position_to_fn.iterkeys()])

        if self.stack == 'MD635':
            # fluro
            F_series = {int(slide_name.split('_')[1]): x for slide_name, x in self.slide_position_to_fn.items() if slide_name.split('_')[0] == 'F'}
            sorted_fns = []
            for i in sorted(set(F_series.keys())):
                sorted_fns += [F_series[i][pos] for pos in range(1, 4)]
        else:
            if self.stack == 'MD639':

                IHC_series = {int(np.ceil(int(slide_name.split('_')[1])/2.)): x for slide_name, x in self.slide_position_to_fn.items() if int(slide_name.split('_')[1]) % 2 == 0}
                N_series = {int(np.ceil(int(slide_name.split('_')[1])/2.)): x for slide_name, x in self.slide_position_to_fn.items() if int(slide_name.split('_')[1]) % 2 == 1}

            else:

                IHC_series = {int(slide_name.split('_')[1]): x for slide_name, x in self.slide_position_to_fn.items() if slide_name.split('_')[0] == 'IHC'}
                N_series = {int(slide_name.split('_')[1]): x for slide_name, x in self.slide_position_to_fn.items() if slide_name.split('_')[0] == 'N'}

            sorted_fns = []
            for i in sorted(set(IHC_series.keys() + N_series.keys())):
                if i in N_series and i in IHC_series:
                    for pos in range(1, 4):
                        sorted_fns.append(N_series[i][pos])
                        sorted_fns.append(IHC_series[i][pos])
                elif i in N_series:
                    sorted_fns += [N_series[i][pos] for pos in range(1, 4)]
                elif i in IHC_series:
                    sorted_fns += [IHC_series[i][pos] for pos in range(1, 4)]

        self.sorted_filenames = [fn for fn in sorted_fns if fn != 'Nonexisting']

        self.update_sorted_sections_gscene_from_sorted_filenames()

    def save_everything(self):

        # Dump preprocessing info
        placeholder_indices = [idx+1 for idx, fn in enumerate(self.sorted_filenames) if fn == 'Placeholder']
        placeholder_slide_positions = [(slide_name, pos) for slide_name, x in self.slide_position_to_fn.iteritems() for pos, fn in x.iteritems() if fn == 'Placeholder']
        rescan_indices = [idx+1 for idx, fn in enumerate(self.sorted_filenames) if fn == 'Rescan']
        rescan_slide_positions = [(slide_name, pos) for slide_name, x in self.slide_position_to_fn.iteritems() for pos, fn in x.iteritems() if fn == 'Rescan']

        ul_pos = self.sorted_sections_gscene.corners['ul'].scenePos()
        lr_pos = self.sorted_sections_gscene.corners['lr'].scenePos()
        ul_x = int(ul_pos.x())
        ul_y = int(ul_pos.y())
        lr_x = int(lr_pos.x())
        lr_y = int(lr_pos.y())

        info = {'placeholder_indices': placeholder_indices,
        'placeholder_slide_positions': placeholder_slide_positions,
        'rescan_indices': rescan_indices,
        'rescan_slide_positions': rescan_slide_positions,
        'sorted_filenames': self.sorted_filenames,
        'slide_position_to_fn': self.slide_position_to_fn,
        'first_section': self.first_section,
        'last_section': self.last_section,
        'anchor_fn': self.anchor_fn,
        # 'bbox': (ul_x, lr_x, ul_y, lr_y) #xmin,xmax,ymin,ymax
        'bbox': (ul_x, ul_y, lr_x+1-ul_x, lr_y+1-ul_y) #xmin,ymin,w,h
        }

        import datetime
        timestamp = datetime.datetime.now().strftime("%m%d%Y%H%M%S")
        pickle.dump(info, open(self.stack_data_dir + '/%(stack)s_preprocessInfo_%(timestamp)s.pkl' % {'stack': self.stack, 'timestamp':timestamp}, 'w'))

        execute_command('cd %(stack_data_dir)s && rm -f %(stack)s_preprocessInfo.pkl && ln -s %(stack)s_preprocessInfo_%(timestamp)s.pkl %(stack)s_preprocessInfo.pkl' % {'stack': self.stack, 'timestamp':timestamp, 'stack_data_dir':self.stack_data_dir})

        self.save_crop()
        self.save_sorted_filenames()
        self.save()


    def send_info_gordon(self):
        # Upload cropbox file, sorted filenames file, anchor file
        execute_command(('scp %(identity_file)s %(stack_data_dir)s/%(stack)s_cropbox.txt %(remote_data_store)s:%(stack_data_dir_remote)s/ &&'
                        'scp %(identity_file)s %(stack_data_dir)s/%(stack)s_anchor.txt %(remote_data_store)s:%(stack_data_dir_remote)s/ &&'
                        'scp %(identity_file)s %(stack_data_dir)s/%(stack)s_sorted_filenames.txt %(identity_file)s %(remote_data_store)s:%(stack_data_dir_remote)s/') %\
                        dict(stack=self.stack, stack_data_dir=self.stack_data_dir, identity_file=self.identity_file, stack_data_dir_remote=self.stack_data_dir_remote))


    # def send_info_workstation(self):
    #     pass

    def send_to_workstation(self):

        commands_on_brainstem_download_metadata = \
        ('cd %(workstation_data_dir)s && mkdir %(stack)s; cd %(stack)s &&'
        'scp dm:%(stack_data_dir_remote)s/%(stack)s_cropbox.txt . &&'
        'scp dm:%(stack_data_dir_remote)s/%(stack)s_sorted_filenames.txt . &&'
        'scp dm:%(stack_data_dir_remote)s/%(stack)s_anchor.txt . &&'
        'mkdir %(stack)s_elastix_output; scp dm:%(stack_data_dir_remote)s/%(stack)s_elastix_output/%(stack)s_transformsTo_anchor.pkl %(stack)s_elastix_output/') \
        % dict(stack=self.stack,
                workstation_data_dir='/media/yuncong/BstemAtlasData/CSHL_data_processed/',
                stack_data_dir_remote=self.stack_data_dir_remote)

        commands_gordon_tar_sorted_saturation = \
        ('cd %(stack_data_dir_remote)s &&'
        'tar -cf %(stack)s_lossless_sorted_aligned_cropped_saturation.tar %(stack)s_lossless_sorted_aligned_cropped_saturation') \
        % dict(stack=self.stack,
                stack_data_dir_remote=self.stack_data_dir_remote)

        commands_on_brainstem_download_sorted_saturation = \
        ('cd %(workstation_data_dir)s && mkdir %(stack)s; cd %(stack)s &&'
        'rm -rf %(stack)s_lossless_sorted_aligned_cropped_saturation &&'
        'scp -r %(identity_file)s %(remote_data_store)s:%(stack_data_dir_remote)s/%(stack)s_lossless_sorted_aligned_cropped_saturation.tar . &&'
        'tar -xf %(stack)s_lossless_sorted_aligned_cropped_saturation.tar') \
        % dict(stack=self.stack,
                workstation_data_dir='/media/yuncong/BstemAtlasData/CSHL_data_processed/',
                stack_data_dir_remote=self.stack_data_dir_remote)

        commands_on_brainstem_download_unsorted_saturation = \
        ('cd %(workstation_data_dir)s && mkdir %(stack)s; cd %(stack)s &&'
        'rm -rf %(stack)s_lossless_unsorted_alignedTo_%(anchor_fn)s_cropped_saturation &&'
        'scp -r dm:%(stack_data_dir_remote)s/%(stack)s_lossless_unsorted_alignedTo_%(anchor_fn)s_cropped_saturation .') \
        % dict(stack=self.stack,
                workstation_data_dir='/media/yuncong/BstemAtlasData/CSHL_data_processed/',
                stack_data_dir_remote=self.stack_data_dir_remote,
                anchor_fn=self.anchor_fn)

        commands_gordon_tar_sorted_compressed = \
        ('cd %(stack_data_dir_remote)s &&'
        'tar -cf %(stack)s_lossless_sorted_aligned_cropped_compressed.tar %(stack)s_lossless_sorted_aligned_cropped_compressed') \
        % dict(stack=self.stack,
                stack_data_dir_remote=self.stack_data_dir_remote)

        commands_on_brainstem_download_sorted_compressed = \
        ('cd %(workstation_data_dir)s && mkdir %(stack)s; cd %(stack)s &&'
        'rm -rf %(stack)s_lossless_sorted_aligned_cropped_compressed &&'
        'scp -r %(identity_file)s %(remote_data_store)s:%(stack_data_dir_remote)s/%(stack)s_lossless_sorted_aligned_cropped_compressed.tar . &&'
        'tar -xf %(stack)s_lossless_sorted_aligned_cropped_compressed.tar') \
        % dict(stack=self.stack,
                workstation_data_dir='/media/yuncong/BstemAtlasData/CSHL_data_processed/',
                stack_data_dir_remote=self.stack_data_dir_remote)

        commands_on_brainstem_download_unsorted_compressed = \
        ('cd %(workstation_data_dir)s && mkdir %(stack)s; cd %(stack)s &&'
        'rm -rf %(stack)s_lossless_unsorted_alignedTo_%(anchor_fn)s_cropped_compressed &&'
        'scp -r dm:%(stack_data_dir_remote)s/%(stack)s_lossless_unsorted_alignedTo_%(anchor_fn)s_cropped_compressed .') \
        % dict(stack=self.stack,
                workstation_data_dir='/media/yuncong/BstemAtlasData/CSHL_data_processed/',
                stack_data_dir_remote=self.stack_data_dir_remote,
                anchor_fn=self.anchor_fn)

        commands_gordon_tar_masks = \
        ('cd %(stack_data_dir_remote)s &&'
        'tar -cf %(stack)s_mask_sorted_aligned_cropped.tar %(stack)s_mask_sorted_aligned_cropped') \
        % dict(stack=self.stack,
                stack_data_dir_remote=self.stack_data_dir_remote)

        commands_on_brainstem_download_sorted_masks = \
        ('cd %(workstation_data_dir)s && mkdir %(stack)s; cd %(stack)s &&'
        'rm -rf %(stack)s_mask_sorted_aligned_cropped &&'
        'scp -r %(identity_file)s %(remote_data_store)s:%(stack_data_dir_remote)s/%(stack)s_mask_sorted_aligned_cropped.tar . &&'
        'tar -xf %(stack)s_mask_sorted_aligned_cropped.tar') \
        % dict(stack=self.stack,
                workstation_data_dir='/media/yuncong/BstemAtlasData/CSHL_data_processed/',
                stack_data_dir_remote=self.stack_data_dir_remote)

        commands_on_brainstem_download_unsorted_masks = \
        ('cd %(workstation_data_dir)s && mkdir %(stack)s; cd %(stack)s &&'
        'rm -rf %(stack)s_mask_unsorted_alignedTo_%(anchor_fn)s_cropped &&'
        'scp -r dm:%(stack_data_dir_remote)s/%(stack)s_mask_unsorted_alignedTo_%(anchor_fn)s_cropped .') \
        % dict(stack=self.stack,
                workstation_data_dir='/media/yuncong/BstemAtlasData/CSHL_data_processed/',
                stack_data_dir_remote=self.stack_data_dir_remote,
                anchor_fn=self.anchor_fn)

        # execute_command('ssh dm \"%(cmd)s\"' % dict(cmd=commands_gordon_tar_sorted_saturation))
        # execute_command('ssh brainstem \"%(cmd)s\"' % dict(cmd=commands_on_brainstem_download_sorted_saturation))
        execute_command('ssh brainstem \"%(cmd)s\"' % dict(cmd=commands_on_brainstem_download_unsorted_saturation))
        #
        # execute_command('ssh dm \"%(cmd)s\"' % dict(cmd=commands_gordon_tar_sorted_compressed))
        # execute_command('ssh brainstem \"%(cmd)s\"' % dict(cmd=commands_on_brainstem_download_sorted_compressed))
        # execute_command('ssh brainstem \"%(cmd)s\"' % dict(cmd=commands_on_brainstem_download_unsorted_compressed))

        execute_command('ssh brainstem \"%(cmd)s\"' % dict(cmd=commands_on_brainstem_download_metadata))

        # execute_command('ssh dm \"%(cmd)s\"' % dict(cmd=commands_gordon_tar_masks))
        # execute_command('ssh brainstem \"%(cmd)s\"' % dict(cmd=commands_on_brainstem_download_sorted_masks))
        execute_command('ssh brainstem \"%(cmd)s\"' % dict(cmd=commands_on_brainstem_download_unsorted_masks))


    def confirm_order(self):
        sort_json = self.web_service.convert_to_request('confirm_order',
                        stack=self.stack, sorted_filenames=self.sorted_filenames, anchor_fn=self.anchor_fn)

        # Download sorted data folder symbolic links
        download_sorted_thumbnails_symlinks_cmd = ('ssh %(identity_file)s %(remote_data_store)s \"cd %(stack_data_dir_remote)s && tar -cf %(stack)s_thumbnail_sorted_aligned.tar %(stack)s_thumbnail_sorted_aligned\" && '
                'cd %(thumbnail_data_dir)s && mkdir %(stack)s ; cd %(stack)s &&'
                'scp -r %(identity_file)s %(remote_data_store)s:%(stack_data_dir_remote)s/%(stack)s_thumbnail_sorted_aligned.tar . &&'
                'rm -rf %(stack)s_thumbnail_sorted_aligned && tar -xf %(stack)s_thumbnail_sorted_aligned.tar &&'
                'rm -r %(stack)s_thumbnail_sorted_aligned.tar') %\
                dict(stack=self.stack, stack_data_dir=self.stack_data_dir, stack_data_dir_remote=self.stack_data_dir_remote, identity_file=self.identity_file, remote_data_store=self.remote_data_store, remote_host=self.remote_host, thumbnail_data_dir=thumbnail_data_dir)
                # 'ssh %(identity_file)s %(remote_data_store)s rm %(stack_data_dir_remote)s/%(stack)s_thumbnail_sorted_aligned.tar') % \

        execute_command(download_sorted_thumbnails_symlinks_cmd)

        self.statusBar().showMessage('Aligned cropped thumbnail images downloaded.')

        # Download sorted thumbnail cropped data folder symbolic links
        download_sorted_thumbnails_symlinks_cmd = ('ssh %(identity_file)s %(remote_data_store)s \"cd %(stack_data_dir_remote)s && tar -cf %(stack)s_thumbnail_sorted_aligned_cropped.tar %(stack)s_thumbnail_sorted_aligned_cropped\" && '
                'cd %(thumbnail_data_dir)s && mkdir %(stack)s ; cd %(stack)s &&'
                'scp -r %(identity_file)s %(remote_data_store)s:%(stack_data_dir_remote)s/%(stack)s_thumbnail_sorted_aligned_cropped.tar . &&'
                'rm -rf %(stack)s_thumbnail_sorted_aligned_cropped && tar -xf %(stack)s_thumbnail_sorted_aligned_cropped.tar &&'
                'rm -r %(stack)s_thumbnail_sorted_aligned_cropped.tar') %\
                dict(stack=self.stack, stack_data_dir=self.stack_data_dir, stack_data_dir_remote=self.stack_data_dir_remote, identity_file=self.identity_file, remote_data_store=self.remote_data_store, remote_host=self.remote_host, thumbnail_data_dir=thumbnail_data_dir)
                # 'ssh %(identity_file)s %(remote_data_store)s rm %(stack_data_dir_remote)s/%(stack)s_thumbnail_sorted_aligned_cropped.tar') % \

        execute_command(download_sorted_thumbnails_symlinks_cmd)

        # Download sorted lossless aligned cropped compressed data folder symbolic links
        execute_command(('ssh %(identity_file)s %(remote_data_store)s \"cd %(stack_data_dir_remote)s && tar -cf %(stack)s_lossless_sorted_aligned_cropped_compressed.tar %(stack)s_lossless_sorted_aligned_cropped_compressed\" && '
                        'cd %(data_dir)s && mkdir %(stack)s ; cd %(stack)s &&'
                        'scp -r %(identity_file)s %(remote_data_store)s:%(stack_data_dir_remote)s/%(stack)s_lossless_sorted_aligned_cropped_compressed.tar . &&'
                        'rm -rf %(stack)s_lossless_sorted_aligned_cropped_compressed && tar -xf %(stack)s_lossless_sorted_aligned_cropped_compressed.tar &&'
                        'rm -r %(stack)s_lossless_sorted_aligned_cropped_compressed.tar') %\
                        dict(stack=self.stack, data_dir=data_dir, identity_file=self.identity_file, remote_data_store=self.remote_data_store, stack_data_dir_remote=self.stack_data_dir_remote))
				# 'ssh %(identity_file)s %(remote_data_store)s rm %(stack_data_dir_remote)s/%(stack)s_lossless_sorted_aligned_cropped_compressed.tar') % \

        # Download unsorted lossless aligned cropped data MANUALLY !!

        # self.send_to_workstation()

        self.save_everything()


    def update_sorted_sections_gscene_from_sorted_filenames(self):

        if not hasattr(self, 'currently_showing'):
            self.currently_showing = 'original'

        self.valid_section_filenames = self.get_valid_sorted_filenames()
        self.valid_section_indices = [self.sorted_filenames.index(fn)+1 for fn in self.valid_section_filenames]

        if not hasattr(self, 'anchor_fn'):

            anchor_fp = self.stack_data_dir + '/%(stack)s_anchor.txt' % dict(stack=self.stack)
            if os.path.exists(anchor_fp):
                with open(anchor_fp) as f:
                    self.set_anchor(f.readline().strip())
            else:
                shapes = Parallel(n_jobs=16)(delayed(identify_shape)(os.path.join(RAW_DATA_DIR, self.stack, img_fn + '.' + self.tb_fmt)) for img_fn in self.valid_section_filenames)
                largest_idx = np.argmax([h*w for h, w in shapes])
                print 'largest section is ', self.valid_section_filenames[largest_idx]
                self.set_anchor(self.valid_section_filenames[largest_idx])
                print self.valid_section_filenames[largest_idx]

        if self.currently_showing == 'original':

            ordered_image_feeder_labels = range(1, len(self.sorted_filenames)+1)
            self.ordered_image_feeder = ImageDataFeeder('image feeder', stack=self.stack, sections=ordered_image_feeder_labels, use_data_manager=False)
            self.ordered_image_feeder.set_images(labels=ordered_image_feeder_labels,
                                                filenames=[os.path.join(self.thumbnails_dir, filename)
                                                        for filename in self.sorted_filenames],
                                                downsample=32)
            self.ordered_image_feeder.set_downsample_factor(32)

            if self.sorted_sections_gscene.active_i is not None:
                active_i = self.sorted_sections_gscene.active_i
            else:
                active_i = 2

            self.sorted_sections_gscene.set_bad_sections(self.get_bad_sections())
            self.sorted_sections_gscene.set_data_feeder(self.ordered_image_feeder)
            self.sorted_sections_gscene.set_active_section(active_i)

        elif self.currently_showing == 'aligned':

            self.aligned_images_feeder = ImageDataFeeder('aligned image feeder', stack=self.stack,
                                                    sections=self.valid_section_indices, use_data_manager=False)
            self.aligned_images_dir = self.stack_data_dir + '/%(stack)s_thumbnail_unsorted_alignedTo_%(anchor_fn)s/' % {'stack': self.stack, 'anchor_fn':self.anchor_fn}
            # aligned_image_filenames = [os.path.join(self.aligned_images_dir, '%(stack)s_%(fn)s_aligned.tif' % \
            #                             {'stack':self.stack, 'fn': self.sorted_filenames[i]}) for i in self.valid_section_indices]

            aligned_image_filenames = [os.path.join(self.aligned_images_dir, '%(fn)s_thumbnail_alignedTo_%(anchor_fn)s.tif' % \
                                        {'fn': fn, 'anchor_fn': self.anchor_fn}) for fn in self.valid_section_filenames]

            self.aligned_images_feeder.set_images(self.valid_section_indices, aligned_image_filenames, downsample=32, load_with_cv2=False)
            self.aligned_images_feeder.set_downsample_factor(32)

            active_i = self.sorted_sections_gscene.active_i
            self.sorted_sections_gscene.set_data_feeder(self.aligned_images_feeder)
            self.sorted_sections_gscene.set_active_i(active_i)

        elif self.currently_showing == 'mask_contour':

            self.maskContourViz_images_feeder = ImageDataFeeder('mask contoured image feeder', stack=self.stack,
                                                sections=self.valid_section_indices, use_data_manager=False)
            self.maskContourViz_images_dir = self.stack_data_dir + '/%(stack)s_maskContourViz_unsorted/' % {'stack': self.stack}
            # aligned_image_filenames = [os.path.join(self.aligned_images_dir, '%(stack)s_%(fn)s_aligned.tif' % \
            #                             {'stack':self.stack, 'fn': self.sorted_filenames[i]}) for i in self.valid_section_indices]

            maskContourViz_image_filenames = [os.path.join(self.maskContourViz_images_dir, '%(fn)s_mask_contour_viz.tif' % {'fn': fn})
                                        for fn in self.valid_section_filenames]

            self.maskContourViz_images_feeder.set_images(self.valid_section_indices, maskContourViz_image_filenames, downsample=32, load_with_cv2=False)
            self.maskContourViz_images_feeder.set_downsample_factor(32)

            active_i = self.sorted_sections_gscene.active_i
            self.sorted_sections_gscene.set_data_feeder(self.maskContourViz_images_feeder)
            self.sorted_sections_gscene.set_active_i(active_i)


    def save_sorted_filenames(self):

        # dump to disk
        with open(self.stack_data_dir + '/%(stack)s_sorted_filenames.txt' % {'stack': self.stack}, 'w') as f:
            for i, fn in enumerate(self.sorted_filenames):
                f.write(fn + ' ' + str(i+1) + '\n') # index starts from 1

        self.statusBar().showMessage('Sorted filename list saved.')


    def load_sorted_filenames(self):
        self.sorted_filenames = []
        with open(self.stack_data_dir + '/%(stack)s_sorted_filenames.txt' % {'stack': self.stack}, 'r') as f:
            for line in f.readlines():
                fn, idx = line.split()
                self.sorted_filenames.append(fn)
        self.statusBar().showMessage('Sorted filename list is loaded.')

        self.update_sorted_sections_gscene_from_sorted_filenames()

    def load_slide_position_map(self):
        fn = self.stack_data_dir + '/%(stack)s_slide_position_to_fn.pkl' % {'stack': self.stack}
        if os.path.exists(fn):
            self.slide_position_to_fn = pickle.load(open(fn, 'r'))
            self.statusBar().showMessage('Slide position to image filename mapping is loaded.')
        else:
            self.statusBar().showMessage('Cannot load slide position to image filename mapping - File does not exists.')

    def save(self):

        pickle.dump(self.slide_position_to_fn, open(self.stack_data_dir + '/%(stack)s_slide_position_to_fn.pkl' % {'stack': self.stack}, 'w') )



    def get_bad_sections(self):
        # return bad section indices, in sorted list
        return [idx+1 for idx, fn in enumerate(self.sorted_filenames) if fn == 'Placeholder' or fn == 'Rescan']

    def download(self):

        execute_command("""mkdir %(local_data_dir)s/%(stack)s; scp %(identity_file)s %(remote_data_store)s:%(remote_data_dir)s/%(stack)s/*.%(tb_fmt)s %(local_data_dir)s/%(stack)s/""" % \
                        {'remote_data_dir': REMOTE_RAW_DATA_DIR,
                        'local_data_dir': RAW_DATA_DIR,
                        'stack': self.stack,
                        'tb_fmt': self.tb_fmt})

        execute_command("""scp -r %(identity_file)s %(remote_data_store)s:%(remote_data_dir)s/macros_annotated/%(stack)s/ %(local_data_dir)s/macros_annotated/""" % \
                        {'remote_data_dir': REMOTE_RAW_DATA_DIR,
                        'local_data_dir': RAW_DATA_DIR,
                        'stack': self.stack})

        execute_command("""scp -r %(identity_file)s %(remote_data_store)s:%(remote_data_dir)s/macros/%(stack)s/ %(local_data_dir)s/macros/""" % \
                        {'remote_data_dir': REMOTE_RAW_DATA_DIR,
                        'local_data_dir': RAW_DATA_DIR,
                        'stack': self.stack})

    def generate_masks(self):

        self.web_service.convert_to_request('generate_masks',
                                    stack=self.stack, filenames=self.get_valid_sorted_filenames(),
                                    tb_fmt=self.tb_fmt)

        # execute_command("""rm -rf %(remote_data_dir)s/%(stack)s/%(stack)s_mask_unsorted && scp -r %(identity_file)s %(remote_data_store)s:%(remote_data_dir)s/%(stack)s/%(stack)s_mask_unsorted %(local_data_dir)s/%(stack)s/""" % \
        #                 {'remote_data_dir': '/home/yuncong/CSHL_data_processed',
        #                 'local_data_dir': '/home/yuncong/CSHL_data_processed',
        #                 'stack': self.stack})

        execute_command("""rm -rf %(remote_data_dir)s/%(stack)s/%(stack)s_maskContourViz_unsorted && scp -r %(identity_file)s %(remote_data_store)s:%(remote_data_dir)s/%(stack)s/%(stack)s_maskContourViz_unsorted %(local_data_dir)s/%(stack)s/""" % \
                        {'remote_data_dir': remote_thumbnail_data_dir,
                        'local_data_dir': thumbnail_data_dir,
                        'identity_file' : self.identity_file,
                        'remote_host' : self.remote_host,
                        'remote_data_store' : self.remote_data_store,
                        'stack': self.stack})

    def warp_crop_masks(self):
        ul_pos = self.sorted_sections_gscene.corners['ul'].scenePos()
        lr_pos = self.sorted_sections_gscene.corners['lr'].scenePos()
        ul_x = int(ul_pos.x())
        ul_y = int(ul_pos.y())
        lr_x = int(lr_pos.x())
        lr_y = int(lr_pos.y())

        self.web_service.convert_to_request('warp_crop_masks',
                                            stack=self.stack, filenames=self.get_valid_sorted_filenames(),
                                            x=ul_x, y=ul_y, w=lr_x+1-ul_x, h=lr_y+1-ul_y, anchor_fn=self.anchor_fn)

        execute_command("""rm -rf %(remote_data_dir)s/%(stack)s/%(stack)s_mask_unsorted_alignedTo_%(anchor_fn)s && scp -r %(identity_file)s %(remote_data_store)s:%(remote_data_dir)s/%(stack)s/%(stack)s_mask_unsorted_alignedTo_%(anchor_fn)s %(local_data_dir)s/%(stack)s/""" % \
                        {'remote_data_dir': remote_thumbnail_data_dir,
                        'local_data_dir': thumbnail_data_dir,
                        'identity_file' : self.identity_file,
                        'remote_host' : self.remote_host,
                        'remote_data_store' : self.remote_data_store,
                        'anchor_fn': self.anchor_fn,
                        'stack': self.stack})

        execute_command("""rm -rf %(remote_data_dir)s/%(stack)s/%(stack)s_mask_unsorted_alignedTo_%(anchor_fn)s_cropped && scp -r %(identity_file)s %(remote_data_store)s:%(remote_data_dir)s/%(stack)s/%(stack)s_mask_unsorted_alignedTo_%(anchor_fn)s_cropped %(local_data_dir)s/%(stack)s/""" % \
                        {'remote_data_dir': remote_thumbnail_data_dir,
                        'local_data_dir': thumbnail_data_dir,
                        'identity_file' : self.identity_file,
                        'remote_host' : self.remote_host,
                        'remote_data_store' : self.remote_data_store,
                        'anchor_fn': self.anchor_fn,
                        'stack': self.stack})


    def align(self):
        self.web_service.convert_to_request('align', stack=self.stack, filenames=self.get_valid_sorted_filenames())
        dc = dict(remote_data_dir=self.stack_data_dir_remote, identity_file=self.identity_file, remote_host=self.remote_host, remote_data_store=self.remote_data_store, local_data_dir=self.stack_data_dir, stack=self.stack)

        ## SSH speed is not stable. Performance is alternating: one 5MB/s, the next 800k/s, the next 5MB/s again.
        execute_command(('ssh %(identity_file)s %(remote_host)s \"cd %(remote_data_dir)s && tar -I pigz -cf %(stack)s_elastix_output.tar.gz %(stack)s_elastix_output/*/*.tif\" &&'
                        'scp %(identity_file)s %(remote_data_store)s:%(remote_data_dir)s/%(stack)s_elastix_output.tar.gz %(local_data_dir)s/ &&'
                        'cd %(local_data_dir)s && rm -rf %(stack)s_elastix_output && tar -xf %(stack)s_elastix_output.tar.gz && rm %(stack)s_elastix_output.tar.gz &&'
                        'ssh %(identity_file)s %(remote_host)s rm %(remote_data_dir)s/%(stack)s_elastix_output.tar.gz') % \
                        dict(remote_data_dir=self.stack_data_dir_remote,
                            identity_file=self.identity_file,
                            remote_host=self.remote_host,
                            remote_data_store=self.remote_data_store,
                            local_data_dir=self.stack_data_dir,
                            stack=self.stack))

        self.statusBar().showMessage('Consecutive sections alignment results downloaded.')

    def get_valid_sorted_filenames(self):
        return [fn for fn in self.sorted_filenames if fn != 'Rescan' and fn != 'Placeholder']

    def compose(self):

        with open(os.path.join(thumbnail_data_dir, '%(stack)s/%(stack)s_anchor.txt' % {'stack': self.stack}), 'w') as f:
            f.write(self.anchor_fn)

        self.statusBar().showMessage('Conmpose consecutive alignments...')
        self.web_service.convert_to_request(name='compose', stack=self.stack,
                                            filenames=self.get_valid_sorted_filenames(),
                                            anchor_fn=self.anchor_fn,
                                            tb_fmt=self.tb_fmt,
                                            pad_bg_color=self.pad_bg_color)
        self.statusBar().showMessage('Images aligned.')

        self.statusBar().showMessage('Downloading aligned images ...')

        execute_command(('ssh %(identity_file)s %(remote_host)s \"cd %(remote_data_dir)s && tar -I pigz -cf %(stack)s_thumbnail_unsorted_alignedTo_%(anchor_fn)s.tar.gz %(stack)s_thumbnail_unsorted_alignedTo_%(anchor_fn)s/*.tif\" && '
                        'scp %(identity_file)s %(remote_data_store)s:%(remote_data_dir)s/%(stack)s_thumbnail_unsorted_alignedTo_%(anchor_fn)s.tar.gz %(local_data_dir)s/ &&'
                        'cd %(local_data_dir)s && rm -rf %(stack)s_thumbnail_unsorted_alignedTo_%(anchor_fn)s && tar -xf %(stack)s_thumbnail_unsorted_alignedTo_%(anchor_fn)s.tar.gz && rm %(stack)s_thumbnail_unsorted_alignedTo_%(anchor_fn)s.tar.gz && '
                        'scp %(identity_file)s %(remote_data_store)s:%(remote_data_dir)s/%(stack)s_elastix_output/%(stack)s_transformsTo_%(anchor_fn)s.pkl %(stack)s_elastix_output/ && '
                        'cd %(stack)s_elastix_output && rm -f %(stack)s_transformsTo_anchor.pkl && ln -s %(stack)s_transformsTo_%(anchor_fn)s.pkl %(stack)s_transformsTo_anchor.pkl ') % \
                        dict(remote_data_dir=self.stack_data_dir_remote,
                            local_data_dir=self.stack_data_dir,
                            stack=self.stack,
                            identity_file=self.identity_file,
                            remote_data_store=self.remote_data_store,
                            remote_host=self.remote_host,
                            anchor_fn=self.anchor_fn))

        self.statusBar().showMessage('Aligned images downloaded.')


    def set_first_section(self, i):
        self.first_section = i
        if self.last_section <= self.first_section:
            self.last_section = self.first_section + 1
        self.update_sorted_sections_gscene_label()

    def set_last_section(self, i):
        self.last_section = i
        if self.last_section <= self.first_section:
            self.first_section = self.last_section - 1
        self.update_sorted_sections_gscene_label()

    def set_anchor(self, anchor):
        if isinstance(anchor, int):
            self.anchor_fn = self.sorted_filenames[anchor-1]
        elif isinstance(anchor, str):
            # assert isinstance(anchor, str)
            self.anchor_fn = anchor

        self.update_sorted_sections_gscene_label()

    def sorted_sections_image_updated(self):
        # print self.sorted_filenames[self.sorted_sections_gscene.active_section]
        filename = self.sorted_filenames[self.sorted_sections_gscene.active_section-1]
        self.label_sorted_sections_filename.setText(filename)
        self.label_sorted_sections_index.setText(str(self.sorted_sections_gscene.active_section))
        if filename == 'Placeholder' or filename == 'Rescan':
            return
        assert filename != 'Unknown' and filename != 'Nonexisting'

        # Update slide scene
        slide_name = self.filename_to_slide[filename]
        position = self.slide_position_to_fn[slide_name].keys()[self.slide_position_to_fn[slide_name].values().index(filename)]
        self.slide_gscene.set_active_section(slide_name)

        self.update_sorted_sections_gscene_label()


    def update_sorted_sections_gscene_label(self):

        # print self.sorted_sections_gscene.active_section, self.anchor_fn
        # if self.sorted_sections_gscene.active_section is not None:
        #     print self.sorted_filenames[self.sorted_sections_gscene.active_section-1]

        if self.sorted_sections_gscene.active_section == self.first_section:
            self.label_sorted_sections_status.setText('FIRST')
        elif self.sorted_sections_gscene.active_section == self.last_section:
            self.label_sorted_sections_status.setText('LAST')
        elif hasattr(self, 'anchor_fn') and self.sorted_sections_gscene.active_section is not None and \
            self.sorted_filenames[self.sorted_sections_gscene.active_section-1] == self.anchor_fn:
            self.label_sorted_sections_status.setText('ANCHOR')
        else:
            self.label_sorted_sections_status.setText('')

    def set_status(self, slide_name, position, fn):
        """
        Update slide_position_to_fn variables.
        If active, change content and captions of the specified slide position gscene.
        """

        # old_fn = self.slide_position_to_fn[slide_name][position]
        self.slide_position_to_fn[slide_name][position] = fn

        # # if slide_name == 'N_92':
        # print position
        # print self.slide_position_gscenes[position].data_feeder.all_sections
        # print self.section_image_feeders[slide_name].all_sections

        if slide_name == self.slide_gscene.active_section:
            self.slide_position_gscenes[position].set_active_section(fn)
            self.labels_slide_position_filename[position].setText(fn)

            if hasattr(self, 'sorted_filenames'):
                if fn == 'Placeholder' or fn == 'Rescan' or fn == 'Nonexisting':
                    self.labels_slide_position_index[position].setText('')
                else:
                    if fn in self.sorted_filenames:
                        self.labels_slide_position_index[position].setText(str(self.sorted_filenames.index(fn)+1))
                    else:
                        self.labels_slide_position_index[position].setText('Not in sorted list.')


    def slide_image_updated(self):
        self.setWindowTitle('Slide %(slide_index)s' % {'slide_index': self.slide_gscene.active_section})

        slide_name = self.slide_gscene.active_section
        feeder = self.section_image_feeders[slide_name]

        if slide_name not in self.slide_position_to_fn:
            self.slide_position_to_fn[slide_name] = {p: 'Unknown' for p in [1,2,3]}

        for position, gscene in self.slide_position_gscenes.iteritems():

            gscene.set_data_feeder(feeder)

            if self.slide_position_to_fn[slide_name][position] != 'Unknown':
                self.set_status(slide_name, position, self.slide_position_to_fn[slide_name][position])
            else:
                if position in self.thumbnail_filenames[slide_name]:
                    newest_fn = sorted(self.thumbnail_filenames[slide_name][position].items())[-1][1]
                    self.set_status(slide_name, position, newest_fn)
                else:
                    self.set_status(slide_name, position, 'Nonexisting')

    def show_option_changed(self, index):

        show_option_text = str(self.sender().currentText())
        if show_option_text == 'Original Aligned':
            self.set_show_option('aligned')
        elif show_option_text == 'Original':
            self.set_show_option('original')
        elif show_option_text == 'Mask Contoured':
            self.set_show_option('mask_contour')
        else:
            raise Exception('Not implemented.')

    def set_show_option(self, showing):

        if self.currently_showing == showing:
            return
        else:
            self.currently_showing = showing
            print self.currently_showing
            self.update_sorted_sections_gscene_from_sorted_filenames()

    def slide_position_image_updated(self):
        position = self.sender().id
        # if self.slide_position_gscenes[position].active_section is not None:
        #     self.slide_position_to_fn[self.slide_gscene.active_section][position] = self.slide_position_gscenes[position].active_section
        self.set_status(self.slide_gscene.active_section, position, self.slide_position_gscenes[position].active_section)


    def eventFilter(self, obj, event):

        if event.type() == QEvent.GraphicsSceneMousePress:
            pass

        elif event.type() == QEvent.KeyPress:
            key = event.key()


        return False


if __name__ == "__main__":

    import argparse
    import sys
    import time

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='Data Preprocessing GUI.')

    parser.add_argument("stack_name", type=str, help="stack name")
    args = parser.parse_args()

    from sys import argv, exit
    app = QApplication(argv)

    m = PreprocessGUI(stack=args.stack_name)

    # m.show()
    m.showMaximized()
    # m.raise_()
    exit(app.exec_())
